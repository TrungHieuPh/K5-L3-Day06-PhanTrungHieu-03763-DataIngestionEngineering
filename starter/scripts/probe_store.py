"""Smoke test: ingest -> chunk -> embed -> pgvector upsert + search."""
import os
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import load_dotenv

from src.ingestion import load_pdf, normalize_text
from src.chunking import by_clause
from src.embeddings import LocalSentenceEmbedder
from src.models import DocumentPage
from src.store import PgVectorStore


load_dotenv(Path(__file__).resolve().parents[1] / ".env")
PDF = Path(__file__).resolve().parents[1] / "data" / "bo_luat_lao_dong_45_2019_QH14.pdf"


def main() -> None:
    db_url = os.environ["DATABASE_URL"]

    raw_pages = load_pdf(PDF, "BLLD_45_2019_QH14", "bo_luat_lao_dong_45_2019_QH14.pdf")
    pages = [
        DocumentPage(
            document_id=p.document_id,
            source=p.source,
            page=p.page,
            text=normalize_text(p.text),
            metadata=p.metadata,
        )
        for p in raw_pages
    ]
    chunks = by_clause(pages, min_size=200, max_size=800)
    print(f"chunks: {len(chunks)}")

    emb = LocalSentenceEmbedder()
    print(f"embedder: {emb.model_name} dim={emb.dimensions}")

    vectors = emb.embed_documents([c.text for c in chunks])
    print(f"embedded: {len(vectors)} vectors")

    store = PgVectorStore(db_url, emb.dimensions)
    store.create_schema()
    print("schema ready")

    store.upsert("C", chunks, vectors)
    print("upserted strategy=C")

    queries = [
        ("Khi nào người lao động được nghỉ hưu?", None),
        ("Hợp đồng lao động có mấy loại?", None),
        ("Tuổi nghỉ hưu quy định tại điều nào?", {"article": 169}),
        ("Quy định về hợp đồng lao động trong Chương III", {"chapter_roman": "III"}),
    ]
    for q, filt in queries:
        qv = emb.embed_query(q)
        hits = store.search("C", qv, top_k=3, filters=filt)
        print(f"\nQ: {q}  filters={filt}")
        for h in hits:
            art = h["metadata"].get("article")
            ch = h["metadata"].get("chapter_roman")
            print(
                f"  score={h['score']:+.4f}  art={art}  ch={ch}  id={h['chunk_id']}"
            )
            print(f"    text[:160]={h['text'][:160]!r}")


if __name__ == "__main__":
    main()
