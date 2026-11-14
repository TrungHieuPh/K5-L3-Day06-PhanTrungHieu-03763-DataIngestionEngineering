"""Build the manual-audit sheets (GUIDE §4: coherence, metadata, grounding).

Run from starter/ AFTER `python -m src.run`:
    python scripts/make_audit_sheets.py

Writes results/audit/:
  coherence_sample.json / .md   10 fixed source positions x 3 strategies
  metadata_check.json / .csv    5 test questions x top-3 x 3 strategies,
                                cross-checked by an INDEPENDENT re-parse
  grounding_sample.md           full top-3 text for the 5 test questions

Sampling rules are fixed in code and do not look at any score:
  * coherence: 10 evenly spaced content pages (sorted page IDs), position =
    middle character of the page. If no chunk of some strategy covers that
    character (e.g. a chapter heading between articles), move forward to the
    first character covered by all three strategies.
  * metadata / grounding: every test question, every top-3 chunk.
"""
from __future__ import annotations

import csv
import json
import re
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.run import STRATEGIES, _load_pages  # noqa: E402

OUT = ROOT / "results" / "audit"
DOC_ID = "BLLD_45_2019_QH14"
ROMAN = ["I", "II", "III", "IV", "V", "VI", "VII", "VIII", "IX", "X",
         "XI", "XII", "XIII", "XIV", "XV", "XVI", "XVII"]


# ---------------------------------------------------------------------------
# Independent re-derivation of page / article / chapter (does not reuse the
# chunker's parse_articles or bisect helpers).
# ---------------------------------------------------------------------------
def build_reference(pages):
    texts = [p.text for p in pages]
    joined = "\n".join(texts)
    page_starts, cur = [], 0
    for t in texts:
        page_starts.append(cur)
        cur += len(t) + 1

    # Article headings: "Điều N." at line start, accepted only in strict order 1, 2, 3 ...
    arts, want = [], 1
    for m in re.finditer(r"(?m)^[ \t]*Điều[ \t]+(\d+)\.", joined):
        if int(m.group(1)) == want:
            arts.append((want, m.start()))
            want += 1
    # Chapter headings: "Chương X" at line start, accepted only in roman order.
    chaps, ci = [], 0
    for m in re.finditer(r"(?m)^[ \t]*Chương[ \t]+([IVXL]+)\b", joined):
        if ci < len(ROMAN) and m.group(1) == ROMAN[ci]:
            chaps.append((ROMAN[ci], m.start()))
            ci += 1
    return {"joined": joined, "page_starts": page_starts, "articles": arts, "chapters": chaps}


def _last_le(items, offset):
    best = None
    for key, start in items:
        if start <= offset:
            best = key
        else:
            break
    return best


def page_of(ref, offset):
    return _last_le([(i + 1, s) for i, s in enumerate(ref["page_starts"])], offset)


def article_of(ref, offset):
    return _last_le(ref["articles"], offset)


def articles_overlapping(ref, start, end):
    arts = ref["articles"]
    out = []
    for i, (n, s) in enumerate(arts):
        e = arts[i + 1][1] if i + 1 < len(arts) else len(ref["joined"])
        if s < end and e > start:
            out.append(n)
    return out


def chapter_of_article(ref, art_num):
    art_start = dict(ref["articles"])[art_num]
    return _last_le(ref["chapters"], art_start)


# ---------------------------------------------------------------------------
def coherence_positions(pages, ref, chunks_by_strategy):
    content = sorted(p.page for p in pages if p.text.strip())
    n = len(content)
    picked = [content[round(i * (n - 1) / 9)] for i in range(10)]

    def covered_by_all(pos):
        return all(any(c.metadata["char_start"] <= pos < c.metadata["char_end"] for c in chs)
                   for chs in chunks_by_strategy.values())

    positions = []
    for pg in picked:
        page_text = pages[pg - 1].text
        pos = ref["page_starts"][pg - 1] + len(page_text) // 2
        shifted = 0
        while not covered_by_all(pos) and pos < len(ref["joined"]) - 1:
            pos += 1
            shifted += 1
        positions.append({"page": pg, "offset": pos, "shifted_chars": shifted,
                          "context": ref["joined"][max(0, pos - 40):pos + 40].replace("\n", " ")})
    return positions


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    pages, _ = _load_pages()
    ref = build_reference(pages)
    assert len(ref["articles"]) == 220, len(ref["articles"])
    assert len(ref["chapters"]) == 17, len(ref["chapters"])

    chunks_by_strategy = {k: cfg["fn"](pages) for k, cfg in STRATEGIES.items()}

    # ---------------- coherence ----------------
    positions = coherence_positions(pages, ref, chunks_by_strategy)
    coh = {"rule": __doc__.split("Sampling rules")[1].strip(), "positions": positions, "items": []}
    md = ["# Coherence sample — 10 vị trí cố định × 3 chiến lược", "",
          "Vị trí chọn trước khi chấm (xem quy tắc trong `scripts/make_audit_sheets.py`).", ""]
    for i, p in enumerate(positions, start=1):
        md.append(f"## P{i:02d} — trang {p['page']}, offset {p['offset']} (dịch {p['shifted_chars']} ký tự)")
        md.append(f"Ngữ cảnh: `…{p['context']}…`\n")
        for key, chs in chunks_by_strategy.items():
            cover = [c for c in chs if c.metadata["char_start"] <= p["offset"] < c.metadata["char_end"]]
            c = cover[0]
            m = c.metadata
            coh["items"].append({
                "pos": f"P{i:02d}", "strategy": key, "chunk_id": c.chunk_id,
                "n_covering_chunks": len(cover), "article": m.get("article"),
                "articles": m.get("articles"), "chars": len(c.text), "text": c.text,
            })
            md.append(f"### P{i:02d} · {key} · `{c.chunk_id}` · {len(c.text)} ký tự · "
                      f"Điều {m.get('articles')} · phủ bởi {len(cover)} chunk")
            md.append("```text\n" + c.text + "\n```\n")
    (OUT / "coherence_sample.json").write_text(json.dumps(coh, ensure_ascii=False, indent=2), encoding="utf-8")
    (OUT / "coherence_sample.md").write_text("\n".join(md), encoding="utf-8")

    # ---------------- metadata + grounding ----------------
    meta_rows = []
    g_md = ["# Grounding sample — 5 câu test × top-3 × 3 chiến lược", "",
            "Thang GUIDE §4.4: 0 = không có bằng chứng; 1 = có nhưng thiếu điều kiện/ngữ cảnh; "
            "2 = đủ để trả lời và truy nguồn. Chấm trên top-3 gộp lại.", ""]
    for key in STRATEGIES:
        traces = [json.loads(l) for l in (ROOT / "results" / f"traces_{key}.jsonl").open(encoding="utf-8")]
        for t in traces:
            if t["split"] != "test":
                continue
            g_md.append(f"## {t['question_id']} · {key} · filter={t['filter']}")
            g_md.append(f"**Hỏi:** {t['question']}  \n**Đáp án:** {t['expected_answer']}  \n"
                        f"**Gold:** Điều {t['gold_article']}  \n**Evidence:** {t['evidence_quote']}\n")
            for h in t["hits"]:
                cs, ce = h["char_start"], h["char_end"]
                src_slice = ref["joined"][cs:ce]
                text_ok = h["text"].strip() == src_slice.strip()
                ts = cs + (len(src_slice) - len(src_slice.lstrip()))
                te = ce - (len(src_slice) - len(src_slice.rstrip()))
                exp = {
                    "page_start": page_of(ref, ts),
                    "page_end": page_of(ref, te - 1),
                    "article": article_of(ref, ts),
                    "articles": articles_overlapping(ref, ts, te),
                }
                if key == "A" and exp["article"] not in exp["articles"]:
                    exp["article"] = exp["articles"][0]
                exp["chapter_roman"] = chapter_of_article(ref, h["article"]) if h["article"] else None
                present = all(h.get(f) not in (None, "") for f in
                              ("document_id", "source", "page", "article", "chapter_roman"))
                checks = {
                    "document_id_ok": h["document_id"] == DOC_ID,
                    "source_ok": h["source"] == "bo_luat_lao_dong_45_2019_QH14.pdf",
                    "text_matches_source_span": text_ok,
                    "page_ok": h["page"] == exp["page_start"] and h["page_start"] == exp["page_start"]
                               and h["page_end"] == exp["page_end"],
                    "article_ok": h["article"] == exp["article"],
                    "articles_ok": sorted(h["articles"]) == sorted(exp["articles"]),
                    "chapter_ok": h["chapter_roman"] == exp["chapter_roman"],
                }
                correct = all(checks.values())
                # A chunk crossing a chapter boundary carries only its primary chapter.
                chaps_spanned = sorted({chapter_of_article(ref, a) for a in exp["articles"]},
                                       key=ROMAN.index)
                meta_rows.append({
                    "strategy": key, "question_id": t["question_id"], "rank": h["rank"],
                    "chunk_id": h["chunk_id"], "document_id": h["document_id"], "source": h["source"],
                    "page": h["page"], "page_start": h["page_start"], "page_end": h["page_end"],
                    "article": h["article"], "articles": h["articles"], "chapter_roman": h["chapter_roman"],
                    "expected": exp, **checks, "chapters_spanned": chaps_spanned,
                    "fields_present": present, "complete_and_correct": present and correct,
                    "filter": t["filter"], "filter_compliant_query": t["filter_compliant"],
                })
                g_md.append(f"### rank {h['rank']} · `{h['chunk_id']}` · score {h['score']} · "
                            f"Điều {h['articles']} · trang {h['page_start']}–{h['page_end']} · "
                            f"chứa evidence={h['contains_evidence']} · hit={h['is_hit']}")
                g_md.append("```text\n" + h["text"] + "\n```\n")
    (OUT / "metadata_check.json").write_text(json.dumps(meta_rows, ensure_ascii=False, indent=2), encoding="utf-8")
    cols = ["strategy", "question_id", "rank", "chunk_id", "document_id", "source", "page", "page_start",
            "page_end", "article", "articles", "chapter_roman", "chapters_spanned", "document_id_ok",
            "source_ok", "text_matches_source_span", "page_ok", "article_ok", "articles_ok", "chapter_ok",
            "fields_present", "complete_and_correct", "filter", "filter_compliant_query"]
    with (OUT / "metadata_check.csv").open("w", encoding="utf-8-sig", newline="") as f:
        w = csv.DictWriter(f, fieldnames=cols, extrasaction="ignore")
        w.writeheader()
        for r in meta_rows:
            w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v)
                        for k, v in r.items()})
    (OUT / "grounding_sample.md").write_text("\n".join(g_md), encoding="utf-8")

    # ---------------- console summary ----------------
    print("Coherence positions:", [(p["page"], p["offset"], p["shifted_chars"]) for p in positions])
    for key in STRATEGIES:
        rows = [r for r in meta_rows if r["strategy"] == key]
        ok = sum(r["complete_and_correct"] for r in rows)
        bad = [(r["question_id"], r["rank"], [k for k in ("page_ok", "article_ok", "articles_ok",
               "chapter_ok", "text_matches_source_span") if not r[k]]) for r in rows if not r["complete_and_correct"]]
        multi_ch = sum(len(r["chapters_spanned"]) > 1 for r in rows)
        print(f"  metadata {key}: {ok}/{len(rows)} complete & correct; errors={bad}; "
              f"records spanning >1 chapter={multi_ch}")
    print(f"Wrote {OUT.relative_to(ROOT)}/")


if __name__ == "__main__":
    main()
