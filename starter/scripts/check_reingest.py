"""Re-ingest check: loading the same version twice must not duplicate rows,
and a changed document must not leave stale chunks behind.

Uses a throw-away strategy key so the real A/B/C indexes are untouched.
Run from starter/:  python scripts/check_reingest.py
Writes results/reingest_check.json.
"""
import json
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

from src.chunking import by_article
from src.embeddings import LocalSentenceEmbedder
from src.run import _load_pages
from src.store import PgVectorStore

TEST_KEY = "_reingest_test"


def main() -> None:
    load_dotenv(ROOT / ".env")
    pages, _ = _load_pages()
    chunks = by_article(pages)
    emb = LocalSentenceEmbedder()
    vectors = emb.embed_documents([c.text for c in chunks])
    store = PgVectorStore(os.environ["DATABASE_URL"], emb.dimensions)
    store.create_schema()
    store.delete_strategy(TEST_KEY)

    steps = []
    store.upsert(TEST_KEY, chunks, vectors)
    steps.append({"step": "first ingest", "expected": len(chunks), **store.count(TEST_KEY)})
    store.upsert(TEST_KEY, chunks, vectors)
    steps.append({"step": "re-ingest same version", "expected": len(chunks), **store.count(TEST_KEY)})

    # Simulate a new document version that has fewer chunks (first 100 Điều only).
    changed = chunks[:100]
    store.upsert(TEST_KEY, changed, vectors[:100])
    steps.append({"step": "ingest changed version (100 chunks)", "expected": 100, **store.count(TEST_KEY)})

    store.delete_strategy(TEST_KEY)
    steps.append({"step": "cleanup", "expected": 0, **store.count(TEST_KEY)})

    ok = all(s["rows"] == s["expected"] == s["distinct_chunk_ids"] for s in steps)
    real = {k: store.count(k) for k in ("A", "B", "C")}
    result = {
        "mechanism": (
            "upsert() runs DELETE FROM chunks WHERE strategy=? AND document_id=? and then "
            "INSERTs the new chunks in ONE transaction; PRIMARY KEY (strategy, chunk_id) "
            "rejects duplicates. Re-running is idempotent and a changed document fully "
            "replaces its old chunks."
        ),
        "steps": steps,
        "passed": ok,
        "real_index_counts": real,
    }
    (ROOT / "results" / "reingest_check.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for s in steps:
        print(f"  {s['step']:<40} rows={s['rows']:>4} distinct={s['distinct_chunk_ids']:>4} expected={s['expected']:>4}")
    print(f"  real indexes: {real}")
    print("PASSED" if ok else "FAILED")
    if not ok:
        sys.exit(1)


if __name__ == "__main__":
    main()
