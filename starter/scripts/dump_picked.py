"""Dump selected articles to a clean JSON file for inspection."""
import json
from pathlib import Path

ART = Path(__file__).resolve().parents[1] / "results" / "articles.json"
OUT = Path(__file__).resolve().parents[1] / "results" / "picked_articles.json"

PICKS = [1, 13, 14, 20, 21, 34, 35, 36, 60, 90, 91, 98, 105, 106, 107,
         111, 112, 113, 115, 124, 125, 137, 138, 139, 143, 160, 169, 188, 220]


def main() -> None:
    data = json.loads(ART.read_text(encoding="utf-8"))
    by_num = {a["article_number"]: a for a in data["articles"]}
    picked = []
    for n in PICKS:
        a = by_num.get(n)
        if not a:
            picked.append({"article_number": n, "found": False})
            continue
        picked.append({
            "article_number": a["article_number"],
            "article_title": a["article_title"],
            "chapter_roman": a["chapter_roman"],
            "chapter_title": a["chapter_title"],
            "page_start": a["page_start"],
            "page_end": a["page_end"],
            "char_count": a["char_count"],
            "text_preview": a["text"][:1500],
        })
    OUT.write_text(json.dumps(picked, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
