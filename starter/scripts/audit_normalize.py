"""Count remaining intra-syllable space artifacts after normalize across all pages."""
import re
import sys
from pathlib import Path
from collections import Counter

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import load_pdf, normalize_text

PDF = Path(__file__).resolve().parents[1] / "data" / "bo_luat_lao_dong_45_2019_QH14.pdf"

# Any word-fragment + space + diacritic/modified vowel = suspicious artifact.
SUSPECT = re.compile(
    r"\b([a-zA-ZđĐ]{1,4})\s+("
    r"[ăâêôơư"
    r"àáảãạằắẳẵặầấẩẫậ"
    r"èéẻẽẹềếểễệ"
    r"ìíỉĩị"
    r"òóỏõọồốổỗộờớởỡợ"
    r"ùúủũụừứửữự"
    r"ỳýỷỹỵ"
    r"]\w*)"
)


def main() -> None:
    pages = load_pdf(PDF, "BLLD_45_2019_QH14", "bo_luat_lao_dong_45_2019_QH14.pdf")
    counter: Counter[str] = Counter()
    total_matches = 0
    for p in pages:
        norm = normalize_text(p.text)
        for m in SUSPECT.finditer(norm):
            frag = f"{m.group(1)} {m.group(2)}"
            counter[frag] += 1
            total_matches += 1
    print(f"total_pages={len(pages)}")
    print(f"total suspect matches = {total_matches}")
    print(f"unique fragments = {len(counter)}")
    print("top 30:")
    for frag, n in counter.most_common(30):
        print(f"  {n:4d}  '{frag}'")


if __name__ == "__main__":
    main()
