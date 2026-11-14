"""Parse the Bộ Luật Lao động PDF into a per-article index for benchmark design.

Output: starter/results/articles.json
Each entry: {article_number, chapter_roman, chapter_title, article_title, text, pages, char_count}
"""
import json
import re
import sys
import unicodedata
from pathlib import Path
from pypdf import PdfReader

PDF = Path(__file__).resolve().parents[1] / "data" / "bo_luat_lao_dong_45_2019_QH14.pdf"
OUT = Path(__file__).resolve().parents[1] / "results" / "articles.json"

HEADER_RE = re.compile(r"CÔNG BÁO/Số 993 \+ 994/Ngày 26-12-2019\s*\d*", re.MULTILINE)
VIET_LETTER = r"[A-Za-zÀ-ỹĐđ]"
INNER_SPACE_RE = re.compile(rf"(?<={VIET_LETTER})\s+(?={VIET_LETTER})")  # not safe; only for intra-word
MULTI_SPACE_RE = re.compile(r"[ \t]+")

CHAPTER_RE = re.compile(r"Chương\s+(?P<roman>[IVXLCDM]+)\s*\n+\s*(?P<title>[^\n]+)", re.IGNORECASE)
ARTICLE_START_RE = re.compile(r"(?m)^\s*Điều\s+(?P<num>\d+)\s*\.\s*(?P<title>[^\n]+)")


def basic_normalize(text: str) -> str:
    text = unicodedata.normalize("NFC", text)
    text = HEADER_RE.sub("", text)
    text = text.replace("\r\n", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text


def fix_intra_word_spaces(text: str) -> str:
    """Heuristic: PDF extraction splits Vietnamese words at kerning boundaries.
    Example: 'ng ười' -> 'người'. We only glue when both sides look like Vietnamese letters
    AND the right fragment is a lowercase continuation (length >=1)."""
    # Run several passes because fixes can compound (e.g., "tr ường h ợp")
    prev = None
    cur = text
    passes = 0
    while prev != cur and passes < 5:
        prev = cur
        # glue when left ends with a letter (lowercase) and right starts with a lowercase letter
        cur = re.sub(r"([a-zà-ỹđ])\s+(?=[a-zà-ỹđ])", lambda m: m.group(1), cur)
        passes += 1
    return cur


def main() -> None:
    reader = PdfReader(str(PDF))
    per_page_text: list[str] = []
    for page in reader.pages:
        t = page.extract_text() or ""
        per_page_text.append(t)

    # Build per-page normalized text and a (char_offset -> page) map
    norm_pages: list[str] = []
    for t in per_page_text:
        t_norm = basic_normalize(t)
        norm_pages.append(t_norm)

    full_text = "\n".join(norm_pages)
    # For evidence quoting we want human-readable text WITHOUT aggressive intra-word fix,
    # because the fix is lossy at word boundaries. Keep two versions.
    full_text_fixed = fix_intra_word_spaces(full_text)

    # Build a page index on the ORIGINAL joined text. Map char offset -> page number (1-based).
    page_boundaries: list[int] = []  # cumulative end-offset per page in `full_text`
    cursor = 0
    for i, t in enumerate(norm_pages):
        cursor += len(t) + (1 if i < len(norm_pages) - 1 else 0)  # +1 for the join "\n"
        page_boundaries.append(cursor)

    def offset_to_page(offset: int) -> int:
        for idx, end in enumerate(page_boundaries):
            if offset < end:
                return idx + 1
        return len(page_boundaries)

    # Find chapters
    chapters: list[dict] = []
    for m in CHAPTER_RE.finditer(full_text):
        chapters.append({
            "roman": m.group("roman"),
            "title": re.sub(r"\s+", " ", m.group("title")).strip(),
            "offset": m.start(),
        })

    # Find articles (on the full_text_fixed version so titles are readable)
    article_matches = list(ARTICLE_START_RE.finditer(full_text_fixed))
    articles: list[dict] = []
    for i, m in enumerate(article_matches):
        num = int(m.group("num"))
        title = re.sub(r"\s+", " ", m.group("title")).strip()
        start = m.start()
        end = article_matches[i + 1].start() if i + 1 < len(article_matches) else len(full_text_fixed)
        body = full_text_fixed[start:end]
        body_clean = re.sub(r"\n+", "\n", body).strip()
        # Determine chapter by nearest preceding chapter marker IN ORIGINAL full_text (offsets differ a bit)
        # Approximate: use same offset on full_text (lengths are close).
        chap = None
        for c in chapters:
            if c["offset"] <= start:
                chap = c
            else:
                break
        articles.append({
            "article_number": num,
            "article_title": title,
            "chapter_roman": chap["roman"] if chap else None,
            "chapter_title": chap["title"] if chap else None,
            "start_offset": start,
            "end_offset": end,
            "page_start": offset_to_page(start),
            "page_end": offset_to_page(end - 1),
            "char_count": len(body_clean),
            "text": body_clean,
        })

    # De-duplicate: keep only strictly increasing article numbers (drop "Điều N" references inside bodies)
    # Strategy: first-occurrence policy already captured by sequential matches, but some bodies
    # contain forward references. We trust ARTICLE_START_RE at ^ of a line, but PDF join can produce false positives.
    # Keep only if article_number > previous AND article_title has at least 3 chars.
    cleaned: list[dict] = []
    last_num = 0
    for a in articles:
        if a["article_number"] <= last_num:
            continue
        if len(a["article_title"]) < 3:
            continue
        cleaned.append(a)
        last_num = a["article_number"]

    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps({
        "chapters": chapters,
        "articles_count": len(cleaned),
        "articles": cleaned,
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Chapters detected: {len(chapters)}")
    print(f"Articles kept: {len(cleaned)} (min={cleaned[0]['article_number']}, max={cleaned[-1]['article_number']})")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
