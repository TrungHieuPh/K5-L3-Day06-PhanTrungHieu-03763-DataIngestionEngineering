"""Day 06 pipeline: ingest -> 3 chunking strategies -> embed -> pgvector -> evaluate.

Run from `starter/`:  python -m src.run

Outputs (results/):
  ingest_log.json      per-page char counts + empty/error pages
  evidence_check.json  every evidence_quote located verbatim in its gold Điều
  traces_{A,B,C}.jsonl full top-3 trace per question (text + metadata + labels)
  summary.json         run manifest, chunk stats, resources, metrics, filter ablation
"""
from __future__ import annotations

import hashlib
import importlib.metadata as md
import json
import os
import platform
import statistics
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from dotenv import load_dotenv

from .chunking import by_article, by_clause, concat_with_offsets, fixed_size, parse_articles
from .embeddings import LocalSentenceEmbedder
from .evaluation import evaluate_query, find_evidence_span, summarize
from .ingestion import load_pdf, normalize_text
from .models import Chunk, DocumentPage
from .store import PgVectorStore


ROOT = Path(__file__).resolve().parents[1]
PDF_PATH = ROOT / "data" / "bo_luat_lao_dong_45_2019_QH14.pdf"
MANIFEST_PATH = ROOT / "data" / "manifest.json"
QUESTIONS_PATH = ROOT / "benchmark" / "questions.json"
RESULTS_DIR = ROOT / "results"
DOCUMENT_ID = "BLLD_45_2019_QH14"
SOURCE_NAME = "bo_luat_lao_dong_45_2019_QH14.pdf"
TOP_K = 3

STRATEGIES: dict[str, dict[str, Any]] = {
    "A": {
        "name": "fixed_size(500,50)",
        "params": {"chunking": "fixed_size", "size_chars": 500, "overlap_chars": 50},
        "fn": lambda pages: fixed_size(pages, 500, 50),
    },
    "B": {
        "name": "by_article",
        "params": {"chunking": "by_article", "size_limit": None},
        "fn": lambda pages: by_article(pages),
    },
    "C": {
        "name": "by_clause(200,800)",
        "params": {"chunking": "by_clause", "min_chars": 200, "max_chars": 800},
        "fn": lambda pages: by_clause(pages, min_size=200, max_size=800),
    },
}


def _map_filter(q_filter: dict[str, Any] | None) -> dict[str, Any] | None:
    """Translate benchmark filter keys to store filter keys."""
    if not q_filter:
        return None
    out: dict[str, Any] = {}
    if "article" in q_filter:
        out["article"] = q_filter["article"]
    if "chapter" in q_filter:
        out["chapter_roman"] = q_filter["chapter"]
    return out or None


def _verify_source_file() -> str:
    """Fail loudly if the PDF is not the exact file recorded in the manifest."""
    digest = hashlib.sha256(PDF_PATH.read_bytes()).hexdigest()
    manifest = json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))
    expected = manifest["sources"][0]["file"]["sha256"]
    if digest != expected:
        raise RuntimeError(f"PDF sha256 {digest} != manifest {expected}")
    return digest


def _load_pages() -> tuple[list[DocumentPage], dict[str, Any]]:
    """Read + normalize every page; return pages and an ingest log."""
    raw_pages = load_pdf(PDF_PATH, DOCUMENT_ID, SOURCE_NAME)
    pages: list[DocumentPage] = []
    page_log: list[dict[str, Any]] = []
    for p in raw_pages:
        try:
            text = normalize_text(p.text)
            status = "ok" if text.strip() else "empty"
            error = None
        except Exception as exc:  # keep going, but record the failure
            text, status, error = "", "error", repr(exc)
        pages.append(DocumentPage(p.document_id, p.source, p.page, text, p.metadata))
        page_log.append(
            {
                "page": p.page,
                "raw_chars": len(p.text),
                "normalized_chars": len(text),
                "status": status,
                "error": error,
            }
        )
    content_pages = sum(1 for e in page_log if e["status"] == "ok")
    problems = [e for e in page_log if e["status"] != "ok"]
    for e in problems:
        print(f"  WARNING page {e['page']}: {e['status']} {e['error'] or ''}".rstrip())
    if content_pages < 30:
        raise RuntimeError(f"Only {content_pages} non-empty pages — lab requires >= 30")
    print(f"Loaded {len(pages)} pages ({content_pages} with text, {len(problems)} empty/error).")
    log = {
        "source": SOURCE_NAME,
        "physical_pages": len(pages),
        "content_pages": content_pages,
        "empty_or_error_pages": [e["page"] for e in problems],
        "total_raw_chars": sum(e["raw_chars"] for e in page_log),
        "total_normalized_chars": sum(e["normalized_chars"] for e in page_log),
        "pages": page_log,
    }
    return pages, log


def _load_questions() -> list[dict[str, Any]]:
    data = json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))
    qs = data["questions"]
    print(f"Loaded {len(qs)} questions from {data['benchmark_name']}.")
    return qs


def _check_evidence(
    questions: list[dict[str, Any]], pages: list[DocumentPage]
) -> dict[str, tuple[int, int]]:
    """Locate each evidence quote inside its gold Điều; raise if any is missing."""
    text, _ = concat_with_offsets(pages)
    spans_by_article = {a["number"]: (a["start"], a["end"]) for a in parse_articles(text)}
    spans: dict[str, tuple[int, int]] = {}
    report: list[dict[str, Any]] = []
    missing: list[str] = []
    for q in questions:
        found = None
        for art in [q["gold_page"], *(q.get("alt_gold_pages") or [])]:
            if art in spans_by_article:
                s, e = spans_by_article[art]
                found = find_evidence_span(text, q["evidence_quote"], s, e)
                if found:
                    break
        report.append(
            {
                "question_id": q["id"],
                "gold_article": q["gold_page"],
                "evidence_chars": len(q["evidence_quote"]),
                "found_in_gold_article": found is not None,
                "char_span": list(found) if found else None,
            }
        )
        if found:
            spans[q["id"]] = found
        else:
            missing.append(q["id"])
    (RESULTS_DIR / "evidence_check.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if missing:
        raise RuntimeError(f"evidence_quote not found verbatim in gold article: {missing}")
    print(f"Evidence check: {len(spans)}/{len(questions)} quotes found verbatim in gold Điều.")
    return spans


def _chunk_stats(chunks: list[Chunk], embedder: LocalSentenceEmbedder) -> dict[str, Any]:
    chars = [len(c.text) for c in chunks]
    tokens = embedder.count_tokens([c.text for c in chunks])
    over = sum(1 for t in tokens if t > embedder.max_seq_length)
    return {
        "n_chunks": len(chunks),
        "chars": {
            "min": min(chars),
            "median": statistics.median(chars),
            "mean": round(statistics.mean(chars), 1),
            "max": max(chars),
            "total": sum(chars),
        },
        "tokens": {
            "median": statistics.median(tokens),
            "mean": round(statistics.mean(tokens), 1),
            "max": max(tokens),
            "total": sum(tokens),
        },
        "n_over_max_seq_length": over,
        "pct_over_max_seq_length": round(over / len(chunks), 4),
        "n_multi_article": sum(1 for c in chunks if len(c.metadata.get("articles", [])) > 1),
        "n_cross_page": sum(
            1 for c in chunks if c.metadata.get("page_start") != c.metadata.get("page_end")
        ),
    }


def _ablation_view(trace: dict[str, Any], filters: dict[str, Any]) -> dict[str, Any]:
    """Compact view of an unfiltered run, plus whether it would have met the filter."""
    return {
        "hit_at_1": trace["hit_at_1"],
        "evidence_hit_at_3": trace["evidence_hit_at_3"],
        "article_hit_at_3": trace["article_hit_at_3"],
        "top_chunk_ids": [h["chunk_id"] for h in trace["hits"]],
        "top_articles": [h["article"] for h in trace["hits"]],
        "top_chapters": [h["chapter_roman"] for h in trace["hits"]],
        "in_scope_count": sum(
            1 for h in trace["hits"] if all(h.get(k) == v for k, v in filters.items())
        ),
    }


def _run_strategy(
    key: str,
    cfg: dict[str, Any],
    pages: list[DocumentPage],
    questions: list[dict[str, Any]],
    evidence_spans: dict[str, tuple[int, int]],
    embedder: LocalSentenceEmbedder,
    store: PgVectorStore,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    t = time.perf_counter()
    chunks = cfg["fn"](pages)
    chunk_s = time.perf_counter() - t
    print(f"\n=== Strategy {key}: {cfg['name']}  (n_chunks={len(chunks)}) ===")
    stats = _chunk_stats(chunks, embedder)

    t = time.perf_counter()
    vectors = embedder.embed_documents([c.text for c in chunks])
    embed_s = time.perf_counter() - t
    print(f"  embed:  {embed_s:6.2f}s  ({len(vectors)} vectors)")

    t = time.perf_counter()
    store.upsert(key, chunks, vectors)
    upsert_s = time.perf_counter() - t
    db_count = store.count(key)
    if db_count["rows"] != len(chunks) or db_count["distinct_chunk_ids"] != len(chunks):
        raise RuntimeError(f"Strategy {key}: DB has {db_count}, expected {len(chunks)} rows")
    print(f"  upsert: {upsert_s:6.2f}s  (db rows={db_count['rows']}, no duplicates)")

    traces: list[dict[str, Any]] = []
    query_times: list[float] = []
    for q in questions:
        filters = _map_filter(q.get("filter"))
        span = evidence_spans.get(q["id"])
        t = time.perf_counter()
        qv = embedder.embed_query(q["question"])
        hits = store.search(key, qv, top_k=TOP_K, filters=filters)
        query_times.append(time.perf_counter() - t)
        trace = evaluate_query(q, hits, filters=filters, evidence_span=span)
        trace["strategy"] = key
        if filters:
            # Ablation: same index, same query, filter removed.
            nf_hits = store.search(key, qv, top_k=TOP_K, filters=None)
            nf_trace = evaluate_query(q, nf_hits, filters=None, evidence_span=span)
            trace["nofilter"] = _ablation_view(nf_trace, filters)
        traces.append(trace)

    avg_q = statistics.mean(query_times)
    max_q = max(query_times)
    print(f"  query:  avg={avg_q*1000:5.1f}ms  max={max_q*1000:5.1f}ms  (n={len(traces)})")

    metrics = summarize(traces)
    filtered = [t for t in traces if "nofilter" in t]
    ablation = {
        "n": len(filtered),
        "with_filter": {
            m: sum(1 for t in filtered if t[f])
            for m, f in (("hit@1", "hit_at_1"), ("evidence_hit@3", "evidence_hit_at_3"), ("article_hit@3", "article_hit_at_3"))
        },
        "without_filter": {
            m: sum(1 for t in filtered if t["nofilter"][f])
            for m, f in (("hit@1", "hit_at_1"), ("evidence_hit@3", "evidence_hit_at_3"), ("article_hit@3", "article_hit_at_3"))
        },
        "without_filter_out_of_scope_chunks": sum(
            TOP_K - t["nofilter"]["in_scope_count"] for t in filtered
        ),
        "without_filter_total_chunks": TOP_K * len(filtered),
    }
    return traces, {
        "label": cfg["name"],
        "params": cfg["params"],
        "chunk_stats": stats,
        "resources": {
            "chunk_s": round(chunk_s, 3),
            "embed_s": round(embed_s, 3),
            "upsert_s": round(upsert_s, 3),
            "avg_query_s": round(avg_q, 4),
            "max_query_s": round(max_q, 4),
            "cost_usd": 0.0,
        },
        "db_count_after_upsert": db_count,
        "metrics": metrics,
        "filter_ablation": ablation,
    }


def _write_traces(traces: list[dict[str, Any]], out_path: Path) -> None:
    with out_path.open("w", encoding="utf-8") as f:
        for t in traces:
            f.write(json.dumps(t, ensure_ascii=False) + "\n")


def _versions() -> dict[str, str]:
    out = {"python": platform.python_version(), "platform": platform.platform()}
    for pkg in ("sentence-transformers", "torch", "transformers", "psycopg", "pypdf", "numpy"):
        try:
            out[pkg] = md.version(pkg)
        except md.PackageNotFoundError:
            out[pkg] = "not installed"
    return out


def _print_comparison(summary: dict[str, Any]) -> None:
    print("\n=== Results (hits / n) ===")
    cols = ("hit@1", "evidence_hit@3", "article_hit@3", "evidence_union_hit@3")
    print(f"{'strat':<6}{'split':<12}" + "".join(f"{c:>22}" for c in cols))
    for key, s in summary["strategies"].items():
        for bucket in ("dev", "test", "filter_only"):
            m = s["metrics"][bucket]
            row = "".join(f"{str(m[c]['hits']) + '/' + str(m['n']):>22}" for c in cols)
            print(f"{key:<6}{bucket:<12}{row}")
    print("\n=== Filter ablation on filter questions (hits / n) ===")
    for key, s in summary["strategies"].items():
        a = s["filter_ablation"]
        print(
            f"  {key}: with filter {a['with_filter']}  without {a['without_filter']}  "
            f"out-of-scope chunks without filter = {a['without_filter_out_of_scope_chunks']}/{a['without_filter_total_chunks']}"
        )


def main() -> None:
    load_dotenv(ROOT / ".env")
    db_url = os.environ["DATABASE_URL"]
    started = datetime.now(timezone.utc)

    sha = _verify_source_file()
    pages, ingest_log = _load_pages()
    (RESULTS_DIR / "ingest_log.json").write_text(
        json.dumps(ingest_log, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    questions = _load_questions()
    evidence_spans = _check_evidence(questions, pages)

    embedder = LocalSentenceEmbedder()
    print(f"Embedder: {embedder.model_name} dim={embedder.dimensions} max_seq_length={embedder.max_seq_length}")

    store = PgVectorStore(db_url, embedder.dimensions)
    store.create_schema()
    server = store.server_info()
    print(f"Store ready: PostgreSQL {server['postgres']} + pgvector {server['pgvector']}")

    strategies: dict[str, Any] = {}
    for key, cfg in STRATEGIES.items():
        traces, strategy_summary = _run_strategy(
            key, cfg, pages, questions, evidence_spans, embedder, store
        )
        _write_traces(traces, RESULTS_DIR / f"traces_{key}.jsonl")
        strategies[key] = strategy_summary

    summary = {
        "run": {
            "started_at_utc": started.isoformat(timespec="seconds"),
            "finished_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "source_sha256": sha,
            "benchmark": json.loads(QUESTIONS_PATH.read_text(encoding="utf-8"))["benchmark_name"],
            "embedding": {
                "provider": "local (sentence-transformers, CPU)",
                "model": embedder.model_name,
                "dimensions": embedder.dimensions,
                "max_seq_length_tokens": embedder.max_seq_length,
                "normalize_embeddings": True,
                "query_document_handling": "same encoder, no prefix, for queries and documents",
            },
            "vector_store": {
                "engine": "PostgreSQL + pgvector (Docker, 127.0.0.1:55433)",
                **server,
                "table": "chunks (PRIMARY KEY strategy, chunk_id)",
                "distance": "cosine (<=>), score = 1 - distance",
                "search": "exact (sequential scan, no ANN index)",
                "top_k": TOP_K,
            },
            "versions": _versions(),
            "cost_usd": 0.0,
        },
        "strategies": strategies,
    }
    (RESULTS_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    _print_comparison(summary)
    print(f"\nWrote results/summary.json, ingest_log.json, evidence_check.json and 3 traces_*.jsonl.")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
