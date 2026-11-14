"""Evaluate retrieval hits against gold articles and evidence quotes.

Metric definitions (GUIDE.md §4.1):

* A retrieved chunk is a **hit** when it belongs to an accepted gold Điều
  AND contains the full `evidence_quote` (whitespace/case-insensitive).
* Hit@1          = top-1 chunk is a hit.
* Evidence Hit@3 = at least one of the top-3 chunks is a hit.

Diagnostics (not replacements for the definitions above):

* article_hit@1 / article_hit@3 — gold Điều matched, evidence ignored.
* evidence_union_hit@3 — the gold-Điều chunks in top-3, taken together,
  cover the evidence span in the source (evidence split across chunks).
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any


_WS_RE = re.compile(r"\s+")


def normalize_for_match(text: str) -> str:
    """NFC + lowercase + collapse any whitespace (incl. newlines) to one space."""
    if not text:
        return ""
    text = unicodedata.normalize("NFC", text).lower()
    return _WS_RE.sub(" ", text).strip()


def find_evidence_span(doc_text: str, quote: str, start: int = 0, end: int | None = None) -> tuple[int, int] | None:
    """Locate `quote` in doc_text[start:end] tolerating whitespace/case differences.

    Returns absolute (char_start, char_end) or None when the quote is absent.
    """
    words = normalize_for_match(quote).split(" ")
    if not words or words == [""]:
        return None
    pattern = re.compile(r"\s+".join(re.escape(w) for w in words), re.IGNORECASE)
    m = pattern.search(unicodedata.normalize("NFC", doc_text), start, len(doc_text) if end is None else end)
    return (m.start(), m.end()) if m else None


def accepted_articles(question: dict[str, Any]) -> list[int]:
    """Return gold_page + any documented alternatives (alt_gold_pages)."""
    golds: list[int] = []
    primary = question.get("gold_page")
    if primary is not None:
        golds.append(int(primary))
    for alt in question.get("alt_gold_pages", []) or []:
        golds.append(int(alt))
    return golds


def _chunk_articles(meta: dict[str, Any]) -> list[int]:
    arts = meta.get("articles")
    if arts:
        return [int(a) for a in arts]
    a = meta.get("article")
    return [int(a)] if a is not None else []


def _covers(spans: list[tuple[int, int]], target: tuple[int, int]) -> bool:
    """True when the union of `spans` fully covers `target`."""
    cursor = target[0]
    for s, e in sorted(spans):
        if s > cursor:
            break
        cursor = max(cursor, e)
        if cursor >= target[1]:
            return True
    return cursor >= target[1]


def _filter_compliant(hits: list[dict[str, Any]], filters: dict[str, Any] | None) -> bool | None:
    """Every returned chunk satisfies every filter key (None when no filter)."""
    if not filters:
        return None
    return all(h["metadata"].get(k) == v for h in hits for k, v in filters.items())


def evaluate_query(
    question: dict[str, Any],
    hits: list[dict[str, Any]],
    filters: dict[str, Any] | None = None,
    evidence_span: tuple[int, int] | None = None,
) -> dict[str, Any]:
    """Score top-3 chunks against gold Điều + evidence; return a full trace dict."""
    top = hits[:3]
    accepted = accepted_articles(question)
    norm_evidence = normalize_for_match(question.get("evidence_quote", "") or "")

    hit_rows: list[dict[str, Any]] = []
    for rank, h in enumerate(top, start=1):
        meta = h["metadata"]
        arts = _chunk_articles(meta)
        gold_match = any(a in accepted for a in arts)
        contains_evidence = bool(norm_evidence) and norm_evidence in normalize_for_match(h["text"])
        hit_rows.append(
            {
                "rank": rank,
                "chunk_id": h["chunk_id"],
                "score": round(float(h["score"]), 4),
                "document_id": h.get("document_id"),
                "source": h.get("source"),
                "page": h.get("page"),
                "page_start": meta.get("page_start"),
                "page_end": meta.get("page_end"),
                "article": meta.get("article"),
                "articles": arts,
                "chapter_roman": meta.get("chapter_roman"),
                "char_start": meta.get("char_start"),
                "char_end": meta.get("char_end"),
                "gold_article_match": gold_match,
                "contains_evidence": contains_evidence,
                "is_hit": gold_match and contains_evidence,
                "text": h["text"],
            }
        )

    gold_spans = [
        (r["char_start"], r["char_end"])
        for r in hit_rows
        if r["gold_article_match"] and r["char_start"] is not None
    ]
    union_hit = bool(evidence_span) and _covers(gold_spans, evidence_span)
    first_hit = next((r["rank"] for r in hit_rows if r["is_hit"]), None)

    return {
        "question_id": question["id"],
        "split": question["split"],
        "type": question["type"],
        "question": question.get("question"),
        "expected_answer": question.get("expected_answer"),
        "evidence_quote": question.get("evidence_quote"),
        "has_filter": question.get("filter") is not None,
        "filter": question.get("filter"),
        "filters_applied": filters,
        "gold_article": question.get("gold_page"),
        "accepted_articles": accepted,
        "evidence_span": list(evidence_span) if evidence_span else None,
        "n_returned": len(top),
        "hit_at_1": bool(hit_rows) and hit_rows[0]["is_hit"],
        "evidence_hit_at_3": first_hit is not None,
        "evidence_rank": first_hit,
        "article_hit_at_1": bool(hit_rows) and hit_rows[0]["gold_article_match"],
        "article_hit_at_3": any(r["gold_article_match"] for r in hit_rows),
        "evidence_union_hit_at_3": union_hit,
        "filter_compliant": _filter_compliant(top, filters),
        "hits": hit_rows,
    }


_METRIC_FIELDS = {
    "hit@1": "hit_at_1",
    "evidence_hit@3": "evidence_hit_at_3",
    "article_hit@1": "article_hit_at_1",
    "article_hit@3": "article_hit_at_3",
    "evidence_union_hit@3": "evidence_union_hit_at_3",
}


def _aggregate(traces: list[dict[str, Any]]) -> dict[str, Any]:
    n = len(traces)
    out: dict[str, Any] = {"n": n}
    for name, field in _METRIC_FIELDS.items():
        k = sum(1 for t in traces if t[field])
        out[name] = {"hits": k, "rate": round(k / n, 4) if n else None}
    with_filter = [t for t in traces if t["filter_compliant"] is not None]
    k = sum(1 for t in with_filter if t["filter_compliant"])
    out["filter_compliance"] = (
        {"compliant": k, "n": len(with_filter)} if with_filter else "N/A"
    )
    return out


def summarize(traces: list[dict[str, Any]]) -> dict[str, Any]:
    """Aggregate metrics by split and filter subset (counts + rates)."""
    buckets = {
        "all": traces,
        "dev": [t for t in traces if t["split"] == "dev"],
        "test": [t for t in traces if t["split"] == "test"],
        "filter_only": [t for t in traces if t["has_filter"]],
    }
    return {name: _aggregate(bucket) for name, bucket in buckets.items()}
