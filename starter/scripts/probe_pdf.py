"""Probe a PDF to see whether pages have extractable text."""
import sys
from pathlib import Path
from pypdf import PdfReader

PDF = Path(__file__).resolve().parents[1] / "data" / "bo_luat_lao_dong_45_2019_QH14.pdf"
SAMPLE_PAGES = [1, 2, 3, 10, 40, 82, 94]
PREVIEW_CHARS = 600
OUT = Path(__file__).resolve().parents[1] / "results" / "probe_report.txt"


def main() -> None:
    reader = PdfReader(str(PDF))
    total = len(reader.pages)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"File: {PDF}", f"Total pages: {total}", ""]

    for p in SAMPLE_PAGES:
        if p > total:
            lines.append(f"--- page {p}: out of range ---\n")
            continue
        text = reader.pages[p - 1].extract_text() or ""
        stripped = text.strip()
        lines.append(f"--- page {p} | chars={len(stripped)} ---")
        lines.append(stripped[:PREVIEW_CHARS])
        lines.append("")

    all_counts = [len((reader.pages[i].extract_text() or "").strip()) for i in range(total)]
    empty = [i + 1 for i, c in enumerate(all_counts) if c == 0]
    lines.append(f"Empty (chars=0) pages: {empty}")
    lines.append(f"Total chars across all pages: {sum(all_counts)}")

    OUT.write_text("\n".join(lines), encoding="utf-8")
    sys.stdout.reconfigure(encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"Pages with text: {total - len(empty)}/{total}")
    print(f"Total chars: {sum(all_counts)}")


if __name__ == "__main__":
    main()
