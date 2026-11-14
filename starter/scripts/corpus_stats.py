"""Compute checksum + article/chapter counts to populate manifest.json."""
import hashlib
import json
import re
import sys
from pathlib import Path
from pypdf import PdfReader

PDF = Path(__file__).resolve().parents[1] / "data" / "bo_luat_lao_dong_45_2019_QH14.pdf"
OUT = Path(__file__).resolve().parents[1] / "results" / "corpus_stats.json"

ARTICLE_RE = re.compile(r"\bĐiều\s+(\d+)[\.\s]")
CHAPTER_RE = re.compile(r"\bChương\s+([IVXLCDM]+)\b")


def main() -> None:
    reader = PdfReader(str(PDF))
    total_pages = len(reader.pages)

    full_text_parts: list[str] = []
    page_char_counts: list[int] = []
    for page in reader.pages:
        text = page.extract_text() or ""
        full_text_parts.append(text)
        page_char_counts.append(len(text.strip()))

    full_text = "\n".join(full_text_parts)
    full_text_collapsed = re.sub(r"\s+", " ", full_text)

    article_ids = sorted({int(m.group(1)) for m in ARTICLE_RE.finditer(full_text_collapsed)})
    chapter_ids = sorted({m.group(1) for m in CHAPTER_RE.finditer(full_text_collapsed)}, key=len)

    sha256 = hashlib.sha256(PDF.read_bytes()).hexdigest()
    size_bytes = PDF.stat().st_size

    empty_pages = [i + 1 for i, c in enumerate(page_char_counts) if c == 0]
    content_pages = [i + 1 for i, c in enumerate(page_char_counts) if c > 0]

    stats = {
        "file_name": PDF.name,
        "size_bytes": size_bytes,
        "sha256": sha256,
        "physical_pages": total_pages,
        "content_pages_count": len(content_pages),
        "empty_pages": empty_pages,
        "total_characters_stripped": sum(page_char_counts),
        "detected_articles_count": len(article_ids),
        "detected_articles_min_max": [min(article_ids), max(article_ids)] if article_ids else None,
        "detected_chapters": chapter_ids,
    }

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(stats, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
