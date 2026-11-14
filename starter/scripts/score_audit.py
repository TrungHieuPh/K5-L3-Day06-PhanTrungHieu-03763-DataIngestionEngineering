"""Aggregate manual-audit labels into scores (GUIDE §4 dimensions 2–4).

Run from starter/ after make_audit_sheets.py and after labels are written:
    python scripts/score_audit.py

Reads  results/audit/labels.json, coherence_sample.json, metadata_check.json,
       results/summary.json, results/traces_*.jsonl
Writes results/audit/audit_summary.json and audit_summary.md
"""
from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.run import STRATEGIES, _load_pages  # noqa: E402

AUDIT = ROOT / "results" / "audit"
KEYS = list(STRATEGIES)


def _load(name):
    return json.loads((AUDIT / name).read_text(encoding="utf-8"))


def _score_block(labels, key_fields, expected_keys):
    got = {tuple(l[f] for f in key_fields): l for l in labels}
    missing = sorted(set(expected_keys) - set(got))
    if missing:
        raise SystemExit(f"Missing labels for {missing}")
    out = {}
    for s in KEYS:
        scores = [l["score"] for l in labels if l["strategy"] == s]
        c = Counter(scores)
        out[s] = {"n": len(scores), "count_0": c[0], "count_1": c[1], "count_2": c[2],
                  "sum": sum(scores), "mean_of_2": round(sum(scores) / len(scores), 2)}
    return out


def main() -> None:
    labels = _load("labels.json")
    coh_sample = _load("coherence_sample.json")
    meta_rows = _load("metadata_check.json")
    summary = json.loads((ROOT / "results" / "summary.json").read_text(encoding="utf-8"))
    traces = {s: [json.loads(l) for l in (ROOT / "results" / f"traces_{s}.jsonl").open(encoding="utf-8")]
              for s in KEYS}
    test_ids = sorted({t["question_id"] for t in traces["A"] if t["split"] == "test"})

    coherence = _score_block(labels["coherence"], ("pos", "strategy"),
                             [(i["pos"], i["strategy"]) for i in coh_sample["items"]])
    grounding = _score_block(labels["grounding"], ("question_id", "strategy"),
                             [(q, s) for q in test_ids for s in KEYS])

    metadata = {}
    for s in KEYS:
        rows = [r for r in meta_rows if r["strategy"] == s]
        test_filter = [t for t in traces[s] if t["split"] == "test" and t["has_filter"]]
        all_filter = [t for t in traces[s] if t["has_filter"]]
        metadata[s] = {
            "records_checked": len(rows),
            "complete_and_correct": sum(r["complete_and_correct"] for r in rows),
            "errors": [f"{r['question_id']} rank{r['rank']}" for r in rows if not r["complete_and_correct"]],
            "test_filter_compliance": {"compliant": sum(bool(t["filter_compliant"]) for t in test_filter),
                                       "n": len(test_filter)},
            "all_filter_compliance": {"compliant": sum(bool(t["filter_compliant"]) for t in all_filter),
                                      "n": len(all_filter)},
            "filter_ablation": summary["strategies"][s]["filter_ablation"],
        }

    # How often a fixed-size chunk crosses a chapter boundary (limits the chapter filter for A).
    pages, _ = _load_pages()
    chap_of = {}
    for c in STRATEGIES["B"]["fn"](pages):
        chap_of[c.metadata["article"]] = c.metadata["chapter_roman"]
    a_chunks = STRATEGIES["A"]["fn"](pages)
    a_cross_chapter = sum(len({chap_of[a] for a in c.metadata["articles"]}) > 1 for c in a_chunks)

    proxy = {s: summary["strategies"][s]["metrics"]["test"]["evidence_hit@3"] for s in KEYS}
    result = {"label_status": labels["status"], "method": labels["method"],
              "coherence": coherence, "grounding": grounding, "metadata": metadata,
              "grounding_auto_proxy_test_evidence_hit@3": proxy,
              "A_chunks_crossing_chapter_boundary": {"n": a_cross_chapter, "of": len(a_chunks)},
              "metadata_notes": labels["metadata_notes"]}
    (AUDIT / "audit_summary.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    md = ["# Audit summary — coherence, metadata, grounding", "",
          f"> **Trạng thái nhãn:** {labels['status']}", "",
          "## Chunk coherence (10 vị trí × 3 chiến lược, thang 0–2)", "",
          "| Chiến lược | 0 | 1 | 2 | Trung bình /2 |", "|---|---|---|---|---|"]
    for s in KEYS:
        c = coherence[s]
        md.append(f"| {s} | {c['count_0']} | {c['count_1']} | {c['count_2']} | {c['sum']}/{2 * c['n']} = {c['mean_of_2']} |")
    md += ["", "| Vị trí | A | B | C |", "|---|---|---|---|"]
    by = {(l["pos"], l["strategy"]): l for l in labels["coherence"]}
    for p in sorted({l["pos"] for l in labels["coherence"]}):
        md.append(f"| {p} | " + " | ".join(f"{by[(p, s)]['score']} — {by[(p, s)]['reason']}" for s in KEYS) + " |")

    md += ["", "## Metadata usefulness (5 câu test × top-3)", "",
           "| Chiến lược | Đủ & đúng / đã kiểm | Lỗi | Filter compliance (test) | Filter compliance (cả bộ) |",
           "|---|---|---|---|---|"]
    for s in KEYS:
        m = metadata[s]
        md.append(f"| {s} | {m['complete_and_correct']}/{m['records_checked']} | {', '.join(m['errors']) or '—'} | "
                  f"{m['test_filter_compliance']['compliant']}/{m['test_filter_compliance']['n']} | "
                  f"{m['all_filter_compliance']['compliant']}/{m['all_filter_compliance']['n']} |")
    md += ["", "Filter ablation (4 câu có filter, cùng index, bỏ filter):", "",
           "| Chiến lược | Evidence Hit@3 có filter | Evidence Hit@3 không filter | Chunk ngoài phạm vi khi bỏ filter |",
           "|---|---|---|---|"]
    for s in KEYS:
        fa = metadata[s]["filter_ablation"]
        md.append(f"| {s} | {fa['with_filter']['evidence_hit@3']}/{fa['n']} | {fa['without_filter']['evidence_hit@3']}/{fa['n']} | "
                  f"{fa['without_filter_out_of_scope_chunks']}/{fa['without_filter_total_chunks']} |")
    md += ["", f"Chunk A vắt qua ranh giới chương: {a_cross_chapter}/{len(a_chunks)}.", ""]
    md += [f"- {n}" for n in labels["metadata_notes"]]

    md += ["", "## Grounding (5 câu test, top-3 gộp, thang 0–2)", "",
           "| Chiến lược | 0 | 1 | 2 | Trung bình /2 | Proxy Evidence Hit@3 (test) |", "|---|---|---|---|---|---|"]
    for s in KEYS:
        g = grounding[s]
        md.append(f"| {s} | {g['count_0']} | {g['count_1']} | {g['count_2']} | {g['sum']}/{2 * g['n']} = {g['mean_of_2']} | "
                  f"{proxy[s]['hits']}/5 |")
    md += ["", "| Câu | A | B | C |", "|---|---|---|---|"]
    gb = {(l["question_id"], l["strategy"]): l for l in labels["grounding"]}
    for q in test_ids:
        md.append(f"| {q} | " + " | ".join(f"{gb[(q, s)]['score']} — {gb[(q, s)]['reason']}" for s in KEYS) + " |")
    (AUDIT / "audit_summary.md").write_text("\n".join(md) + "\n", encoding="utf-8")

    for s in KEYS:
        print(f"{s}: coherence {coherence[s]['sum']}/{2 * coherence[s]['n']} ({coherence[s]['mean_of_2']})  "
              f"grounding {grounding[s]['sum']}/{2 * grounding[s]['n']} ({grounding[s]['mean_of_2']})  "
              f"metadata {metadata[s]['complete_and_correct']}/{metadata[s]['records_checked']}  "
              f"test-filter {metadata[s]['test_filter_compliance']}")
    print(f"A chunks crossing a chapter boundary: {a_cross_chapter}/{len(a_chunks)}")
    print("Wrote results/audit/audit_summary.{json,md}")


if __name__ == "__main__":
    main()
