"""Unit smoke test for evaluate_query + summarize with handcrafted hits."""
import sys
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.evaluation import evaluate_query, summarize


def mk_hit(chunk_id, article, text, score, chapter_roman=None):
    return {
        "chunk_id": chunk_id,
        "text": text,
        "score": score,
        "metadata": {"article": article, "chapter_roman": chapter_roman},
    }


def main() -> None:
    cases = []

    # Case 1: perfect — top-1 đúng Điều + chứa evidence
    q1 = {
        "id": "q01", "split": "dev", "type": "direct",
        "question": "...", "expected_answer": "...",
        "gold_page": 106,
        "evidence_quote": "Giờ làm việc ban đêm được tính từ 22 giờ đến 06 giờ sáng ngày hôm sau.",
        "filter": None,
    }
    hits1 = [
        mk_hit("c1", 106, "Điều 106. Giờ làm việc ban đêm\nGiờ làm việc ban đêm được tính từ 22 giờ đến 06 giờ sáng ngày hôm sau.", 0.90),
        mk_hit("c2", 107, "Điều 107. Làm thêm giờ ...", 0.70),
        mk_hit("c3", 108, "Điều 108. Làm thêm giờ đặc biệt ...", 0.60),
    ]
    cases.append(evaluate_query(q1, hits1))

    # Case 2: gold ở top-3 nhưng không phải top-1, evidence KHÔNG có trong chunk
    q2 = {
        "id": "q02", "split": "dev", "type": "paraphrase",
        "gold_page": 139,
        "evidence_quote": "Lao động nữ được nghỉ thai sản trước và sau khi sinh con là 06 tháng",
        "filter": None,
    }
    hits2 = [
        mk_hit("c4", 140, "Điều 140 nói về bảo đảm việc làm cho lao động nữ nghỉ thai sản.", 0.80),
        mk_hit("c5", 139, "Điều 139 nói về chế độ thai sản. (nội dung bị cắt mất câu evidence)", 0.75),
        mk_hit("c6", 141, "Điều 141 nói về trợ cấp khi sinh con.", 0.70),
    ]
    cases.append(evaluate_query(q2, hits2))

    # Case 3: miss hoàn toàn, có filter
    q3 = {
        "id": "q23", "split": "test", "type": "metadata_filter",
        "gold_page": 125,
        "evidence_quote": "quấy rối tình dục tại nơi làm việc",
        "filter": {"article": 125},
    }
    hits3 = [
        mk_hit("c7", 999, "Điều 999 placeholder.", 0.50),
    ]
    cases.append(evaluate_query(q3, hits3))

    # Case 4: không có evidence_quote (edge case)
    q4 = {
        "id": "q99", "split": "dev", "type": "direct",
        "gold_page": 10, "evidence_quote": "", "filter": None,
    }
    hits4 = [mk_hit("c8", 10, "Điều 10 ...", 0.9)]
    cases.append(evaluate_query(q4, hits4))

    # Case 5: evidence có trong chunk nhưng chunk thuộc SAI Điều -> không phải hit (định nghĩa strict)
    q5 = {
        "id": "q98", "split": "test", "type": "direct",
        "gold_page": 106,
        "evidence_quote": "Giờ làm việc ban đêm được tính từ 22 giờ",
        "filter": {"chapter": "VII"},
    }
    hits5 = [mk_hit("c9", 105, "... Giờ làm việc ban đêm được tính từ 22 giờ ...", 0.9, "VII")]
    cases.append(evaluate_query(q5, hits5, filters={"chapter_roman": "VII"}))

    print("=== Per-query traces ===")
    for t in cases:
        print(
            f"  {t['question_id']}  split={t['split']}  gold={t['gold_article']}  "
            f"top_articles={[h['article'] for h in t['hits']]}  "
            f"hit@1={t['hit_at_1']}  ev@3={t['evidence_hit_at_3']}  "
            f"art@3={t['article_hit_at_3']}  ev_rank={t['evidence_rank']}  "
            f"filter_ok={t['filter_compliant']}"
        )

    expected = {
        "q01": (True, True, True),
        "q02": (False, False, True),
        "q23": (False, False, False),
        "q99": (False, False, True),
        "q98": (False, False, False),
    }
    for t in cases:
        got = (t["hit_at_1"], t["evidence_hit_at_3"], t["article_hit_at_3"])
        assert got == expected[t["question_id"]], (t["question_id"], got)
    assert cases[-1]["filter_compliant"] is True
    print("\nAll metric-definition assertions passed.")

    print("\n=== summarize ===")
    summary = summarize(cases)
    for bucket, metrics in summary.items():
        print(f"  {bucket}: {metrics}")


if __name__ == "__main__":
    main()
