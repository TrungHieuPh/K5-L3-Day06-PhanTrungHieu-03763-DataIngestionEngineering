# Benchmark — BLLD_45_2019_QH14_bench_v2

Bộ câu hỏi đánh giá truy xuất cho corpus **Bộ luật Lao động 45/2019/QH14** (file `starter/data/bo_luat_lao_dong_45_2019_QH14.pdf`, SHA256 trong `starter/data/manifest.json`).

File chính: [`questions.json`](./questions.json) — trạng thái **FINAL v2**. `questions_draft.json` là bản nháp lúc soạn câu hỏi, không dùng để chạy. Bản v1 được lưu tại `starter/results/run_v1_before_fix/questions_v1.json`.

---

## 1. Tổng quan

| Chỉ số | Giá trị | Yêu cầu GUIDE.md |
|---|---|---|
| Tổng câu | 25 | ≥ 20 |
| Dev | 20 | ≥ 15 |
| Test | 5 | ≥ 5 |
| Có filter metadata | 4 (2 dev, 2 test) | ≥ 3, trong đó ≥ 1 test |
| Loại câu | direct 11 · paraphrase 5 · conditional 6 · metadata_filter 4 | đa dạng |

ID bị bỏ trước khi chạy: q13, q22 (lý do trong `removed_questions_history`).

---

## 2. Gold reference unit

- **Chọn:** `article` — số Điều trong Bộ luật.
- `gold_page` trong mỗi câu là **số Điều** (1..220), không phải số trang PDF. Số trang PDF vẫn được lưu trong metadata chunk (`page_start`, `page_end`) để truy nguồn.
- **Lý do:** ranh giới Điều ổn định, không phụ thuộc layout trang; trích dẫn pháp lý thực tế dùng Điều.
- `alt_gold_pages` (nếu có) liệt kê Điều thay thế hợp lệ; hiện không câu nào cần.

---

## 3. Split dev / test

- **Dev (20):** dùng để thử nghiệm và so sánh 3 chiến lược.
- **Test (5):** `q06`, `q17`, `q19`, `q23`, `q27`. Không dùng để chỉnh chiến lược.
- Câu filter trong test: `q23` (Chương VIII), `q27` (Chương XIV).
- ⚠️ **Phơi nhiễm test:** lần chạy v1 đã in điểm test trước khi audit; v2 sửa nhãn/filter của q17, q23, q27 (xem §7). Vì vậy điểm test v2 **không phải holdout độc lập hoàn toàn**. Không có thay đổi chiến lược A/B/C nào dựa trên điểm test.

---

## 4. Tiêu chí chọn chiến lược (chốt trước khi chạy)

1. **Evidence Hit@3**
2. **Hit@1**
3. **Grounding** chấm tay trung bình
4. **Tài nguyên** — thời gian ingest/query, chi phí

Tie-breaker: khi Evidence Hit@3 gần bằng → so Hit@1 → grounding → thời gian/chi phí. Thứ tự này nằm trong `questions.json → selection_criteria_locked_before_test`. Ở v2, hai metric đầu dùng định nghĩa strict của GUIDE (§6).

---

## 5. Cấu trúc một câu hỏi

```jsonc
{
  "id": "q23",
  "type": "metadata_filter",          // direct | paraphrase | conditional | metadata_filter
  "split": "test",                    // dev | test
  "question": "Hành vi quấy rối tình dục ... hình thức cao nhất nào ...?",
  "expected_answer": "Sa thải.",
  "gold_source_id": "BLLD_45_2019_QH14",
  "gold_page": 125,                   // SỐ ĐIỀU, không phải số trang
  "evidence_quote": "Người lao động có hành vi ... được quy định trong nội quy lao động",
  "filter": {"chapter": "VIII"},      // hoặc null
  "filter_context": "Input giả định do người dùng cung cấp TRƯỚC khi truy xuất: ..."
}
```

### Thiết kế filter

- Filter là **phạm vi chương** (`chapter`, số La Mã), lấy từ tiêu đề `Chương …` trong văn bản gốc. 17 ranh giới chương do `src/chunking.py::parse_articles` sinh ra đã được kiểm tra khớp văn bản.
- Giá trị filter là **input giả định người dùng cung cấp trước khi truy xuất** (ghi trong `filter_context`), ví dụ người dùng đang xem chương Kỷ luật lao động. Filter **không** chứa Điều gold: mỗi chương chứa 2–46 Điều.
- Câu không có filter được chạy không filter ở cả 3 chiến lược.

---

## 6. Kiểm chứng evidence và định nghĩa metric

- Mỗi `evidence_quote` là **nguyên văn** trong Điều gold. `python -m src.run` tự kiểm tra lại trước khi chạy và dừng nếu thiếu (kết quả ở `results/evidence_check.json`).
- So khớp sau NFC + lowercase + gộp khoảng trắng.

| Metric | Định nghĩa |
|---|---|
| **hit** (một chunk) | thuộc Điều gold **và** chứa trọn `evidence_quote` |
| **Hit@1** | chunk top-1 là hit |
| **Evidence Hit@3** | ≥ 1 chunk trong top-3 là hit |
| article_hit@1 / @3 *(chẩn đoán)* | chỉ so Điều, bỏ qua evidence |
| evidence_union_hit@3 *(chẩn đoán)* | các chunk thuộc Điều gold trong top-3 **gộp lại** phủ trọn vị trí evidence trong nguồn — đo trường hợp evidence bị tách qua nhiều chunk |
| filter compliance | mọi chunk top-3 thỏa filter / số câu có filter |

### Grounding (chấm tay, theo GUIDE §4.4)

Đánh giá **độ đủ của bằng chứng truy xuất**, không phải độ đúng của câu trả lời LLM. Chấm top-3 của mỗi câu:

- `0` — top-3 không có bằng chứng cho đáp án.
- `1` — có bằng chứng nhưng thiếu điều kiện/ngoại lệ/ngữ cảnh cần thiết.
- `2` — đủ để trả lời và truy được nguồn (Điều, trang).

Câu nhiều điểm (q17, q21, q27): `2` chỉ khi top-3 chứa đủ các điểm a), b), c)…; thiếu điểm thì `1`.

---

## 7. Lịch sử sửa đổi

Ghi đầy đủ trong `questions.json → revision_history`. Tóm tắt v1 → v2 (2026-11-14):

| Câu | Thay đổi | Lý do |
|---|---|---|
| q04, q05, q14, q15, q23, q26 | bỏ dấu `.` cuối evidence | nguồn dùng `;` hoặc `:` — quote cũ không có nguyên văn |
| q17, q21 | thay quote có `...` bằng toàn văn khoản 2 Điều 35 / khoản 2 Điều 107 | quote lược không tồn tại nguyên văn |
| q23, q25, q27 | filter `{article: <Điều gold>}` → `{chapter: VIII / X / XIV}` | filter cũ lộ gold source (vi phạm BENCHMARK.md) |
| q24 | giữ `{chapter: III}`, thêm `filter_context` | — |

---

## 8. Cách dùng

```bash
cd starter
python -m src.run          # kiểm evidence -> chạy A/B/C -> results/traces_*.jsonl, summary.json
```
