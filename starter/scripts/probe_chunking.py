"""Smoke test for chunking strategies A, B, C — prints stats and sample chunks."""
import json
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import load_pdf, normalize_text
from src.chunking import by_article, by_clause, fixed_size
from src.models import DocumentPage

PDF = Path(__file__).resolve().parents[1] / "data" / "bo_luat_lao_dong_45_2019_QH14.pdf"
OUT = Path(__file__).resolve().parents[1] / "results" / "probe_chunking.txt"


def stats(label: str, chunks) -> list[str]:
    sizes = [len(c.text) for c in chunks]
    if not sizes:
        return [f"{label}: NO CHUNKS"]
    sizes_sorted = sorted(sizes)
    median = sizes_sorted[len(sizes) // 2]
    return [
        f"{label}: n={len(chunks)}  "
        f"min={min(sizes)}  median={median}  max={max(sizes)}  "
        f"total_chars={sum(sizes)}"
    ]


def samples_for_article(chunks, article_number: int, limit_text: int = 500) -> list[str]:
    lines = []
    found = [c for c in chunks if c.metadata.get("article") == article_number]
    for c in found:
        lines.append(f"  id={c.chunk_id}  page={c.page}  len={len(c.text)}")
        lines.append(f"  meta={json.dumps({k: v for k, v in c.metadata.items() if k != 'article_title'}, ensure_ascii=False)}")
        lines.append(f"  text[0..{limit_text}]={c.text[:limit_text]!r}")
        lines.append("")
    return lines


def main() -> None:
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

    a_chunks = fixed_size(pages, size=500, overlap=50)
    b_chunks = by_article(pages)
    c_chunks = by_clause(pages, min_size=200, max_size=800)

    out = []
    out.append("=== STATS ===")
    out += stats("A fixed_size(500, 50)", a_chunks)
    out += stats("B by_article", b_chunks)
    out += stats("C by_clause(200, 800)", c_chunks)

    # Chapter / article coverage check for B.
    articles_in_b = sorted({c.metadata["article"] for c in b_chunks})
    missing = sorted(set(range(1, 221)) - set(articles_in_b))
    out.append("")
    out.append(f"B articles found: {len(articles_in_b)} / 220 expected")
    out.append(f"B missing articles: {missing[:30]}{'...' if len(missing) > 30 else ''}")

    chapters_in_b = sorted({c.metadata["chapter_roman"] for c in b_chunks if c.metadata["chapter_roman"]})
    out.append(f"B chapters found: {chapters_in_b}")

    # Spot-check specific articles from benchmark.
    for art in [1, 35, 92, 125, 169, 188, 220]:
        out.append("")
        out.append(f"=== Article {art} — strategy B ===")
        out += samples_for_article(b_chunks, art, limit_text=300)
        out.append(f"=== Article {art} — strategy C ===")
        out += samples_for_article(c_chunks, art, limit_text=300)

    OUT.write_text("\n".join(out), encoding="utf-8")
    print(f"Wrote {OUT}")
    for line in out[:8]:
        print(line)


if __name__ == "__main__":
    main()
