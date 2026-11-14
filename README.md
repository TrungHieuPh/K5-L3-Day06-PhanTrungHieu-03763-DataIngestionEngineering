# Day 06 · Data Ingestion Engineering

**Lab cá nhân** · **4 giờ** · **Dữ liệu tự chọn**

Biến tài liệu thành kho tri thức có thể truy xuất cho AI agent, rồi đo xem cách chuẩn bị dữ liệu nào hiệu quả nhất.

| 📄 Dữ liệu | 🧩 Chiến lược | 🎯 Benchmark |
|---|---|---|
| Tối thiểu **30 trang nội dung** | Tối thiểu **3 cấu hình** | Tối thiểu **20 câu hỏi** |

## Bắt đầu nhanh

Dùng [starter PostgreSQL + pgvector](starter/README.md) để dựng database và hoàn thiện các hàm TODO, hoặc tự chọn vector store tương đương. Starter chỉ là khung: **bạn tự hiện thực pipeline và benchmark**.

## 1. Xây pipeline

![Đọc tài liệu, chuẩn hóa, chia chunk, tạo vector, lưu và kiểm tra](assets/ingestion-pipeline.svg)

Chọn tài liệu được phép sử dụng; giữ **ID tài liệu, nguồn, trang/vị trí** và metadata phù hợp. Dùng embedding model thật qua API hoặc chạy local; lưu và truy xuất bằng pgvector, Qdrant, Chroma hoặc một store tương đương.

## 2. So sánh và đánh giá

![Ba chiến lược được đánh giá trên cùng corpus và benchmark dev/test](assets/benchmark-workflow.svg)

Dùng cùng dữ liệu, model và câu hỏi cho cả ba cấu hình. Tách **15 câu dev / 5 câu test** trước khi chạy; chọn cấu hình trên dev, rồi đánh giá test sau khi cố định. Mỗi câu hỏi cần có đoạn bằng chứng và trang nguồn; thiết kế bộ câu hỏi và đánh giá theo [BENCHMARK.md](BENCHMARK.md).

Đánh giá theo năm khía cạnh: **độ chính xác truy xuất**, **tính mạch lạc của chunk**, **tính hữu dụng của metadata**, **chất lượng grounding** và **tác động của chiến lược dữ liệu**. Giải thích lựa chọn bằng kết quả, ví dụ lỗi và các đánh đổi.

## 3. Chuẩn bị bài nộp

1. Chạy pipeline và lưu cấu hình, kết quả top-3, trace cùng nhãn đánh giá thủ công.
2. Điền [thông tin học viên](STUDENT.md), [nhật ký thí nghiệm](artifacts/experiment_log.csv) và bản sao [mẫu báo cáo cá nhân](report/individual/MSSV_HoTen.md).
3. Kiểm tra mã nguồn, cách chạy, manifest dữ liệu và checklist trong [SUBMISSION.md](SUBMISSION.md).

## Tài liệu hướng dẫn

| Bạn cần tìm | Tài liệu |
|---|---|
| Setup baseline PostgreSQL + pgvector | [starter/README.md](starter/README.md) |
| Các bước làm và cách tính chỉ số | [GUIDE.md](GUIDE.md) |
| Tiến độ trong 4 giờ | [CHECKPOINTS.md](CHECKPOINTS.md) |
| Năm tiêu chí benchmark và bộ câu hỏi | [BENCHMARK.md](BENCHMARK.md) |
| Tiêu chí chấm điểm | [RUBRIC.md](RUBRIC.md) |
| Quy tắc sử dụng dữ liệu, AI và API | [RULES.md](RULES.md) |
| Cách nộp bài | [SUBMISSION.md](SUBMISSION.md) |

[data/format-example.json](data/format-example.json) chỉ minh họa định dạng, không phải corpus đủ điều kiện. Phần xử lý và benchmark do bạn tự hiện thực; không bắt buộc xây chatbot.

---

## Bài nộp — cách tái lập

Corpus: **Bộ luật Lao động 45/2019/QH14**. Báo cáo: [report/individual/03763_PhanTrungHieu.md](report/individual/03763_PhanTrungHieu.md). Học viên: [STUDENT.md](STUDENT.md).

### Đường dẫn dữ liệu và kết quả

| Nội dung | Đường dẫn |
|---|---|
| Corpus (PDF có text layer, public domain) | [starter/data/bo_luat_lao_dong_45_2019_QH14.pdf](starter/data/bo_luat_lao_dong_45_2019_QH14.pdf) |
| Manifest: nguồn, quyền, SHA-256, số trang, quy tắc tính trang | [starter/data/manifest.json](starter/data/manifest.json) |
| Benchmark: 25 câu, 20 dev / 5 test, evidence | [starter/benchmark/questions.json](starter/benchmark/questions.json) và [starter/benchmark/README.md](starter/benchmark/README.md) |
| Code pipeline | [starter/src/](starter/src/) |
| Kết quả: chỉ số, cấu hình và phiên bản | [starter/results/summary.json](starter/results/summary.json) |
| Trace top-3 | `starter/results/traces_{A,B,C}.jsonl` |
| Audit thủ công: coherence, metadata, grounding | [starter/results/audit/](starter/results/audit/) |
| Nhật ký thí nghiệm A/B/C | [artifacts/experiment_log.csv](artifacts/experiment_log.csv) |

### Chạy lại từ đầu

Yêu cầu: Docker Desktop, Python 3.11–3.14, và mạng ở lần đầu để tải Docker image, dependencies và model HuggingFace (`paraphrase-multilingual-MiniLM-L12-v2`, khoảng 450 MB). Model chạy local nên **không cần API key**. Mọi lệnh chạy từ thư mục `starter/`:

```bash
cd starter
python -m venv .venv
# Windows PowerShell: .venv\Scripts\Activate.ps1   |   macOS/Linux: source .venv/bin/activate
python -m pip install -r requirements.txt          # phiên bản đã pin
# Windows PowerShell: Copy-Item .env.example .env   |   macOS/Linux: cp .env.example .env
docker compose -p day6_student_starter up -d --wait
python scripts/check_setup.py                       # kỳ vọng: "Setup OK" (PostgreSQL 16 + pgvector)

python -m src.run                  # ingest → chunk A/B/C → embed → upsert pgvector → truy vấn 25 câu → results/
python scripts/check_reingest.py   # kiểm tra nạp lại không nhân đôi → results/reingest_check.json
python scripts/make_audit_sheets.py   # phiếu chấm tay + kiểm tra metadata độc lập → results/audit/
python scripts/score_audit.py         # gộp nhãn trong results/audit/labels.json → audit_summary.{json,md}
```

Trên một máy Windows 11 chạy CPU, `python -m src.run` mất khoảng 2 phút và tốn 0 USD. Chạy lại sẽ ghi đè các file trong `results/`. Bản ghi lần chạy lỗi trước khi sửa (v1) được giữ ở `starter/results/run_v1_before_fix/`.
