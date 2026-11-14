"""Print selected articles for benchmark design."""
import json
import sys
from pathlib import Path

ART = Path(__file__).resolve().parents[1] / "results" / "articles.json"
PICKS = [1, 13, 14, 20, 21, 34, 35, 36, 60, 69, 90, 91, 98, 105, 106, 107,
         111, 112, 113, 115, 124, 125, 137, 138, 139, 143, 160, 169, 188, 220]


def main() -> None:
    data = json.loads(ART.read_text(encoding="utf-8"))
    by_num = {a["article_number"]: a for a in data["articles"]}
    sys.stdout.reconfigure(encoding="utf-8")
    for n in PICKS:
        a = by_num.get(n)
        if not a:
            print(f"--- Điều {n}: NOT FOUND ---\n")
            continue
        print(f"=== Điều {a['article_number']} | Chương {a['chapter_roman']} ({a['chapter_title']}) | pages {a['page_start']}-{a['page_end']} ===")
        print(a["text"][:1200])
        print("...\n" if len(a["text"]) > 1200 else "\n")


if __name__ == "__main__":
    main()
