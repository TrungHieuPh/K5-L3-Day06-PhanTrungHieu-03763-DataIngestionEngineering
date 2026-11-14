"""Smoke test for ingestion.load_pdf + normalize_text — prints before/after samples."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.ingestion import load_pdf, normalize_text

PDF = Path(__file__).resolve().parents[1] / "data" / "bo_luat_lao_dong_45_2019_QH14.pdf"
OUT = Path(__file__).resolve().parents[1] / "results" / "probe_normalize.txt"

SAMPLE_PAGES = [1, 2, 10, 40, 82, 94]  # first, early content, middle, end, empty page


def preview(s: str, n: int = 400) -> str:
    s = s.replace("\n", "\\n")
    return s[:n] + ("…" if len(s) > n else "")


def main() -> None:
    pages = load_pdf(PDF, document_id="BLLD_45_2019_QH14", source="bo_luat_lao_dong_45_2019_QH14.pdf")
    lines = []
    lines.append(f"total_pages={len(pages)}")
    empty_raw = [p.page for p in pages if not p.text.strip()]
    lines.append(f"empty_raw_pages={empty_raw}")
    for p in pages:
        if p.page not in SAMPLE_PAGES:
            continue
        norm = normalize_text(p.text)
        lines.append("")
        lines.append(f"=== page {p.page} | raw_len={len(p.text)} | norm_len={len(norm)} ===")
        lines.append("--- RAW ---")
        lines.append(preview(p.text, 500))
        lines.append("--- NORMALIZED ---")
        lines.append(preview(norm, 500))
    OUT.write_text("\n".join(lines), encoding="utf-8")
    print(f"Wrote {OUT}")
    print(f"total_pages={len(pages)}  empty_raw_pages={empty_raw}")


if __name__ == "__main__":
    main()
