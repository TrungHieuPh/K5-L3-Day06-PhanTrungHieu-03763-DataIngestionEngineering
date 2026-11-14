# Báo cáo cá nhân — Day 6

Học viên: xem [STUDENT.md](../../STUDENT.md). Corpus: Bộ luật Lao động 45/2019/QH14.

**Lần chạy được báo cáo:** 2026-11-14, 16:12:50 → 16:14:33 UTC, benchmark `BLLD_45_2019_QH14_bench_v2`, SHA-256 nguồn `3c865f3d…43b5b6c`. Mọi số liệu dưới đây được chép từ [results/summary.json](../../starter/results/summary.json) và [results/audit/audit_summary.json](../../starter/results/audit/audit_summary.json); không có số nào được nhập tay.

> **Hai lưu ý cần đọc trước** (chi tiết ở các mục sau):
> 1. **Test không còn là holdout độc lập.** Kết quả test của lần chạy v1 đã bị xem, sau đó nhãn của q17, q23 và q27 đã được sửa ([Cấu hình và benchmark](#cấu-hình-và-benchmark)).
> 2. **Nhãn audit thủ công (coherence, grounding) hiện là bản nháp do AI soạn** và chưa được học viên duyệt ([Sử dụng AI](#sử-dụng-ai-và-cách-kiểm-tra)).

## Dữ liệu và pipeline

- **Chủ đề, nguồn và quyền sử dụng; số trang và quy tắc tính trang**
  - Văn bản: Bộ luật Lao động số 45/2019/QH14, Quốc hội thông qua ngày 20/11/2019, hiệu lực từ 01/01/2021.
  - Nguồn: bản PDF có lớp chữ (text layer), cùng nội dung với bản công bố trên Cổng TTĐT Chính phủ (chinhphu.vn). File `starter/data/bo_luat_lao_dong_45_2019_QH14.pdf`, 1.352.965 byte.
  - Bản scan `45.signed.pdf` đã bị loại vì không có text layer: 100% trang mẫu rỗng khi extract.
  - Quyền: văn bản quy phạm pháp luật không thuộc đối tượng bảo hộ quyền tác giả (khoản 2 Điều 15 Luật Sở hữu trí tuệ), nên được phép lưu PDF trong repo.
  - Số trang: 94 trang vật lý, trong đó **93 trang nội dung**. Quy tắc: một trang được tính khi còn ít nhất 1 ký tự sau khi `strip`. Trang 94 (trang chữ ký điện tử) rỗng nên bị loại và được ghi log.
  - Chi tiết: [data/manifest.json](../../starter/data/manifest.json).

- **Chuẩn hóa, lỗi và giới hạn**
  - Các bước ([src/ingestion.py](../../starter/src/ingestion.py)):
    1. Đọc bằng pypdf.
    2. Chuẩn hóa Unicode NFC.
    3. Bỏ header công báo lặp ở mỗi trang (`CÔNG BÁO/Số 993 + 994/Ngày 26-12-2019 <số trang>`).
    4. Gộp khoảng trắng chen giữa âm tiết do kerning của PDF (`ng ười` → `người`, `tr ường h ợp` → `trường hợp`) bằng 2 lượt regex.
    5. Gộp khoảng trắng thừa nhưng giữ xuống dòng, để nhận diện được dòng `Chương X`, `Điều N.` và khoản `1.`.
  - Kết quả: 201.677 → 189.167 ký tự. Log từng trang: [results/ingest_log.json](../../starter/results/ingest_log.json).
  - Kiểm tra sau chuẩn hóa:
    - [scripts/audit_normalize.py](../../starter/scripts/audit_normalize.py) còn báo 6 cụm nghi vấn. Đọc tay cả 6 đều là cặp từ đúng (`tham ô`, `con ốm`, `cung ứng`, `đang ở`, `nghe ý`, `đang áp`).
    - Quét lỗi gộp nhầm (chữ thường dính liền chữ hoa trong một từ) tìm thấy **1 lỗi chưa sửa**: `choỦy ban` ở Điều 42.
  - Giới hạn:
    - Hai phép kiểm trên chỉ bắt lỗi theo mẫu đã biết, không chứng minh được văn bản sạch hoàn toàn.
    - Số trang dùng trong metadata là trang PDF; số trang in trên công báo bằng trang PDF + 2.
    - Tiêu đề Điều dài hai dòng bị cắt ở dòng đầu trong `article_title`, ví dụ Điều 35 thành "…của người". Đây là trường chỉ dùng để hiển thị, không nằm trong các trường đã kiểm ở mục metadata.
    - Chunk B của Điều 186 dính dòng tiêu đề của Mục kế tiếp ("Mục 2 THẨM QUYỀN…").

- **Embedding, vector store, metric, lệnh chạy và chi phí**

  | Thành phần | Cấu hình |
  |---|---|
  | Embedding | `paraphrase-multilingual-MiniLM-L12-v2`, chạy local trên CPU qua sentence-transformers 6.3.0 (torch 2.15.0, transformers 5.23.0) |
  | Vector | 384 chiều, `normalize_embeddings=True`; dùng cùng encoder cho query và document, không thêm prefix |
  | Giới hạn model | `max_seq_length` = **128 token**: phần văn bản vượt quá bị cắt khi embed (xem phân tích) |
  | Vector store | PostgreSQL 16.16 + pgvector 0.8.7, chạy Docker tại `127.0.0.1:55433`; bảng `chunks` có `PRIMARY KEY (strategy, chunk_id)` |
  | Metric | cosine distance `<=>`, score = 1 − distance; exact search (không dùng ANN index, tổng 1.195 vector); top-3 |
  | Nạp lại | `DELETE` theo (strategy, document_id) rồi `INSERT`, trong một transaction. Kiểm chứng ở [reingest_check.json](../../starter/results/reingest_check.json): 220 → 220 → 100 → 0 dòng, **PASSED** |
  | Lệnh | `python -m src.run` (chạy từ `starter/`; đầy đủ ở [README.md](../../README.md#bài-nộp--cách-tái-lập)) |
  | Chi phí | **0 USD**: model local, không gọi API và không dùng LLM sinh câu trả lời |
  | Thời gian | Toàn bộ lần chạy (3 chiến lược kèm ablation) mất 1 phút 43 giây trên một máy Windows 11, Python 3.14.3 |

- **Metadata bắt buộc, trường lọc bổ sung, nguồn giá trị và lý do chọn**
  - Bắt buộc: `document_id` = `BLLD_45_2019_QH14`; `source` = tên file PDF; `page` = trang PDF nơi chunk bắt đầu, kèm `page_start` và `page_end` cho chunk vắt trang.
  - Bổ sung: `article` (Điều chính), `articles` (mọi Điều chunk chạm tới; quan trọng với A), `article_title`, `chapter_roman`, `chapter_title`, `char_start` và `char_end` (vị trí trong văn bản đã nối).
  - Nguồn giá trị:
    - Điều và chương được parse từ chính dòng tiêu đề `Điều N.` và `Chương X` trong văn bản, không tự gán. Parser kiểm tra đủ 220 Điều và 17 chương.
    - Trang được tính từ vị trí ký tự, tra qua bảng offset của từng trang.
  - Trường filter: **`chapter_roman`**.
    - Luật được tổ chức theo chương, và mỗi chương là một chủ đề (VIII: kỷ luật lao động, XIV: giải quyết tranh chấp…). Người dùng thường biết phạm vi này trước khi hỏi.
    - Không dùng `article` làm filter: nếu người dùng đã biết số Điều thì không cần truy xuất, và filter theo Điều gold sẽ làm lộ đáp án (lỗi này có ở v1 và đã sửa).

## Cấu hình và benchmark

- **A / B / C: tham số cụ thể và khác biệt duy nhất giữa B và C**

  | | A | B | C |
  |---|---|---|---|
  | Chunking | `fixed_size`: cửa sổ ký tự trượt | `by_article`: 1 Điều = 1 chunk | `by_clause`: tách theo khoản bên trong từng Điều |
  | Tham số | 500 ký tự, overlap 50 | không giới hạn độ dài | gộp khoản < 200 ký tự, chia khoản > 800 ký tự; câu dẫn ≥ 200 ký tự thành chunk `#preamble` |
  | Số chunk | 421 | 220 | 554 |
  | Ký tự (min / median / max) | 258 / 500 / 500 | 101 / 718,5 / 7.248 | 19 / 296,5 / 792 |
  | Token median; % chunk > 128 token | 129; 54% | 177,5; **67%** | 78; 15,5% |
  | Metadata, filter, model, top-k | giống nhau | giống nhau | giống nhau |

  - **Khác biệt duy nhất giữa B và C** là độ hạt bên trong một Điều: B giữ cả Điều trong một chunk, C tách theo khoản. Hai chiến lược dùng chung parser Điều/chương, chung các trường metadata, chung quy tắc filter, model và top-k.
  - **So sánh A–B** chỉ đổi phương pháp chunking: cửa sổ cố định so với ranh giới Điều.
  - **Lệch so với ví dụ trong GUIDE** (ví dụ dùng "C = B + filter"):
    - Ở bài này, filter chương được áp cho **cả ba** chiến lược khi câu hỏi có phạm vi chương.
    - Tác động riêng của filter được đo bằng **ablation**: cùng index, cùng query, chỉ bỏ filter. Đây cũng là phép so sánh chỉ đổi đúng một yếu tố, tức "B có filter" so với "B không filter".
    - Lý do giữ thiết kế này: tránh đổi cấu hình sau khi đã thấy kết quả.

- **Benchmark: ≥ 20 câu, phân chia ≥ 15 dev / ≥ 5 test, câu metadata filter và cách kiểm chứng evidence**
  - Gồm **25 câu**: 20 dev và 5 test (q06, q17, q19, q23, q27). Q13 và q22 đã bị loại khỏi bộ câu hỏi; lý do ghi ở `removed_questions_history`.
  - Loại câu: direct 11, paraphrase 5, conditional 6, metadata_filter 4. Q27 vừa là conditional vừa có filter.
  - Câu có filter: 4 câu, gồm q24 (Chương III) và q25 (Chương X) thuộc dev, q23 (Chương VIII) và q27 (Chương XIV) thuộc test. Mỗi câu có `filter_context` giải thích rằng người dùng đã cho phạm vi trước khi truy xuất.
  - Đơn vị gold là **Điều**: trường `gold_page` lưu số Điều, không phải số trang (xem manifest `gold_reference_unit`).
  - Kiểm chứng evidence: [evidence_check.json](../../starter/results/evidence_check.json) cho thấy **25/25** `evidence_quote` có nguyên văn (sau chuẩn hóa khoảng trắng) nằm trong đúng Điều gold, kèm `char_span`.
  - Ngoài ra đã kiểm cả 49 dòng hit: evidence span đều nằm trong khoảng ký tự của chunk, nên không có hit giả do khớp văn bản của Điều khác.
  - Chi tiết: [benchmark/questions.json](../../starter/benchmark/questions.json) và [benchmark/README.md](../../starter/benchmark/README.md).

- **Tiêu chí chọn chiến lược đã chốt trước khi xem test**
  - Thứ tự ưu tiên, tính trên **dev**:
    1. Evidence Hit@3.
    2. Hit@1.
    3. Grounding trung bình.
    4. Tài nguyên (thời gian, chi phí).
  - Ghi trong `selection_criteria_locked_before_test`. Thứ tự này giữ nguyên từ v1.
  - Ở v2, Hit@1 và Evidence Hit@3 dùng định nghĩa strict của GUIDE: chunk thuộc Điều gold **và** chứa trọn evidence.

- **Ghi chú trung thực về tập test (theo RULES)**
  - Lần chạy v1 có 3 lỗi:
    - A thiếu metadata `article`, nên Hit của A luôn bằng 0.
    - 8/25 evidence không có nguyên văn trong nguồn.
    - Filter `{article: <Điều gold>}` làm lộ đáp án ở q23, q25 và q27.
  - Kết quả v1, **có cả test**, đã bị xem trước khi sửa và được lưu ở [results/run_v1_before_fix/](../../starter/results/run_v1_before_fix/).
  - Ở v2, nhãn của câu test q17 (evidence), q23 (evidence và filter) và q27 (filter) đã được sửa; lý do ghi ở `revision_history`. Mục đích là sửa lỗi nhãn, không phải tối ưu chiến lược, nhưng **kết quả test v2 không được coi là kiểm tra độc lập**.
  - File [experiment_log.csv](../../artifacts/experiment_log.csv) được điền sau khi chạy v2. Cột `hypothesis` ghi lý do thiết kế của từng cấu hình, không phải dự đoán đã được niêm phong từ trước.

## Kết quả

Bảng 1: Hit@1 và Evidence Hit@3 dùng định nghĩa strict. "Thời gian index" gồm chunk, embed và upsert. "Query TB" là trung bình trên 25 câu, gồm thời gian embed câu hỏi và tìm kiếm.

| Strategy | Split | Hit@1 (n/N) | Evidence Hit@3 (n/N) | Chunk count | Thời gian | Chi phí |
|---|---|---|---|---|---|---|
| A | dev | 11/20 | 11/20 | 421 | index 32,7 s (embed 32,3 s); query TB 110 ms (max 236 ms) | 0 USD |
| A | test | 2/5 | 2/5 | 421 | (cùng index) | 0 USD |
| **B** | dev | 11/20 | **18/20** | 220 | index 10,7 s (embed 10,4 s); query TB 104 ms (max 183 ms) | 0 USD |
| **B** | test | 1/5 | **3/5** | 220 | (cùng index) | 0 USD |
| C | dev | 10/20 | 13/20 | 554 | index 23,9 s (embed 23,2 s); query TB 144 ms (max 530 ms) | 0 USD |
| C | test | 2/5 | 2/5 | 554 | (cùng index) | 0 USD |

Bảng 2: Audit thủ công. Coherence và grounding dùng **nhãn nháp AI**, chưa được học viên duyệt.

| Strategy | Coherence trung bình /2 (n) | Metadata đủ và đúng (n/N) | Filter tuân thủ (n/N) | Grounding 0/1/2 (số câu) và trung bình /2 |
|---|---|---|---|---|
| A | 0,50 (n = 10; 0/1/2 = 5/5/0) | 15/15 | test 2/2; cả bộ 4/4 | 2/2/1; 0,80 |
| B | **2,00** (n = 10; 0/0/10) | 15/15 | test 2/2; cả bộ 4/4 | 2/0/3; **1,20** |
| C | 1,70 (n = 10; 1/1/8) | 15/15 | test 2/2; cả bộ 4/4 | 3/1/1; 0,60 |

Grounding theo từng câu test (A / B / C):

| Câu | A | B | C |
|---|---|---|---|
| q06 | 2 | 2 | 2 |
| q17 | 0 | 0 | 0 |
| q19 | 1 | 0 | 1 |
| q23 | 0 | 2 | 0 |
| q27 | 1 | 2 | 0 |

Lý do của từng nhãn nằm trong [audit_summary.md](../../starter/results/audit/audit_summary.md).

Chỉ số chẩn đoán (không dùng để chọn chiến lược):

| Strategy | article_hit@3 dev / test | evidence_union_hit@3 dev / test | Ablation filter (4 câu): Evidence Hit@3 có → không filter | Chunk ngoài phạm vi khi bỏ filter |
|---|---|---|---|---|
| A | 16/20 / 4/5 | 11/20 / 2/5 | 1/4 → 1/4 | 4/12 |
| B | 18/20 / 3/5 | 18/20 / 3/5 | **3/4 → 2/4** | 2/12 |
| C | 16/20 / 2/5 | 13/20 / 2/5 | 1/4 → 1/4 | 1/12 |

- `article_hit@3`: có chunk thuộc đúng Điều gold trong top-3, bất kể có chứa evidence hay không.
- `evidence_union_hit@3`: ghép text của top-3 lại thì có chứa evidence.

**Đường dẫn trace, nhãn thủ công và cách chọn mẫu**

- Trace top-3 của cả 25 câu: [traces_A.jsonl](../../starter/results/traces_A.jsonl), [traces_B.jsonl](../../starter/results/traces_B.jsonl), [traces_C.jsonl](../../starter/results/traces_C.jsonl). Mỗi dòng gồm text, score, metadata, `contains_evidence` và `is_hit`; câu có filter có thêm object `nofilter` cho ablation.
- Nhãn và kết quả audit:
  - Nhãn: [results/audit/labels.json](../../starter/results/audit/labels.json).
  - Phiếu chấm: [coherence_sample.md](../../starter/results/audit/coherence_sample.md), [grounding_sample.md](../../starter/results/audit/grounding_sample.md), [metadata_check.csv](../../starter/results/audit/metadata_check.csv).
  - Tổng hợp: [audit_summary.md](../../starter/results/audit/audit_summary.md).
  - Script: [scripts/make_audit_sheets.py](../../starter/scripts/make_audit_sheets.py) sinh phiếu, [scripts/score_audit.py](../../starter/scripts/score_audit.py) tính điểm.
- Cách chọn mẫu (quy tắc viết cứng trong code, không phụ thuộc điểm số):
  - **Coherence**: chọn 10 trang nội dung cách đều nhau (trang 1, 11, 21, 32, 42, 52, 62, 73, 83, 93). Vị trí lấy mẫu là ký tự giữa trang; nếu có chiến lược không phủ ký tự đó (ví dụ dòng tiêu đề chương), dịch tới ký tự đầu tiên mà cả ba chiến lược đều phủ. Chấm chunk đầu tiên phủ vị trí. Thang 0–2.
  - **Metadata**: 5 câu test × top-3 × 3 chiến lược = 45 bản ghi. Mỗi bản ghi được đối chiếu với một bộ parse **độc lập** (regex riêng cho `Điều N.` và `Chương X`, chỉ nhận theo đúng thứ tự, rồi đổi vị trí ký tự sang trang), và kiểm tra text chunk trùng đoạn nguồn.
  - **Grounding**: 5 câu test, chấm trên top-3 gộp lại. Thang của GUIDE §4.4: 0 = không có bằng chứng; 1 = có bằng chứng nhưng thiếu điều kiện hoặc ngữ cảnh; 2 = đủ để trả lời và truy nguồn. Chấm trên evidence truy xuất được, không chấm câu trả lời do LLM sinh.

## Phân tích và kết luận

- **So sánh A–B (chỉ đổi phương pháp chunking)**
  - B hơn A rõ về Evidence Hit@3 trên dev (18/20 so với 11/20), coherence (2,0 so với 0,5) và grounding (1,2 so với 0,8).
  - A thường tìm **đúng Điều** (article_hit@3 dev 16/20) nhưng chunk không chứa **trọn** evidence, vì cửa sổ 500 ký tự cắt ngang khoản. Ghép cả top-3 cũng không bù được (union 11/20).
  - Với 3 câu (q17, q21, q27), evidence dài hơn 500 ký tự, nên A **không thể** đạt strict hit.
  - Hit@1 của A và B bằng nhau (11/20): B thắng nhờ top-3 chứ không nhờ top-1. Lý do: 67% chunk B dài hơn 128 token, nên vector chỉ đại diện cho phần đầu của Điều.

- **So sánh B–C (chỉ đổi độ hạt trong Điều)**
  - Giả thuyết "chunk nhỏ thì Hit@1 cao hơn" **không được dev ủng hộ**: Hit@1 10/20 so với 11/20, và Evidence Hit@3 giảm từ 18/20 xuống 13/20.
  - C tìm đúng Điều (article_hit@3 dev 16/20) nhưng hay trả về **sai khoản**. Với các câu conditional, evidence là cả danh sách điểm, mà C lại chia danh sách đó ra nhiều chunk.
  - Coherence giảm ở vị trí P09: câu dẫn của Điều 199 bị tách thành chunk `#preamble`, nên chunk liệt kê điều kiện mất chủ thể "có quyền đình công", nhận điểm 0.
  - C chỉ thắng khi câu trả lời nằm trọn trong một khoản ở cuối một Điều dài (q19, xem ví dụ 2).

- **Tác động của metadata filter (ablation trên cùng index)**
  - Filter chỉ giúp B: Evidence Hit@3 từ 2/4 lên 3/4. Ở q23, khi không filter thì top-3 có Điều 8 (Chương I) và Điều 165 (Chương XI); khi có filter, Điều 125 vào hạng 3.
  - Với A và C, kết quả không đổi (1/4 → 1/4). Khi bỏ filter, số chunk ngoài phạm vi lần lượt là A 4/12, B 2/12, C 1/12.
  - Filter tuân thủ 4/4 với cả 3 chiến lược.
  - Rủi ro riêng của A: 16/421 chunk vắt qua ranh giới chương nhưng chỉ mang một giá trị `chapter_roman`, nên filter có thể giữ nhầm hoặc loại nhầm phần văn bản thuộc chương khác.
  - Với n = 4, đây chỉ là dấu hiệu, chưa phải kết luận.

- **Ví dụ sai: ID câu, nguồn, nguyên nhân**
  1. **q17** (test, conditional): "Trong trường hợp nào người lao động được đơn phương chấm dứt hợp đồng lao động mà không cần báo trước?"
     - Gold: khoản 2 Điều 35, trang PDF 15–16. Evidence dài 971 ký tự (điểm a–g).
     - **Cả 3 chiến lược đều trượt**; top-1 của cả ba đều là Điều 45 ("Thông báo chấm dứt hợp đồng lao động").
     - A và C không thể chứa trọn evidence vì evidence dài hơn 500 và 800 ký tự. C đã tách khoản 2 thành `art035#k2#p0` và `#p1`.
     - B có chunk Điều 35 chứa trọn evidence (413 token), nhưng evidence bắt đầu ở khoảng **token 161**, nằm ngoài cửa sổ 128 token. Vector của Điều 35 chỉ mã hóa khoản 1 (thời hạn báo trước), nên Điều 35 không vào top-3 (Điều 45, 37, 38).
  2. **q19** (test): "Người lao động tự ý bỏ việc trong bao nhiêu ngày thì có thể bị xử lý kỷ luật sa thải?"
     - Gold: khoản 4 Điều 125, trang 52.
     - **B trượt**: top-3 là Điều 47, 101, 126. Chunk Điều 125 dài 335 token, còn evidence bắt đầu ở khoảng **token 232**: vector chỉ "thấy" khoản 1–2 (trộm cắp, quấy rối…), không thấy "05 ngày cộng dồn".
     - A (`p0233`) và C (`art125#k4`) đều trúng ở hạng 1 vì chunk nhỏ chứa đúng khoản 4.
     - Đây là điểm yếu chính của B và là tình huống chunk nhỏ có lợi.
  3. **q27** (test, filter Chương XIV): "Những loại tranh chấp lao động nào KHÔNG bắt buộc phải qua thủ tục hòa giải…?"
     - Gold: khoản 1 Điều 188, trang 77. Evidence dài 823 ký tự, gồm điểm a–f.
     - B trúng ở hạng 2.
     - **C trượt**: khoản 1 bị chia thành `art188#k1#p0` (744 ký tự) và `#p1` (346 ký tự), nên không chunk nào chứa trọn evidence. Top-3 của C là các khoản khác cùng chương (Điều 193 khoản 4, 6; Điều 189 khoản 5): tuân thủ filter nhưng sai Điều.
     - A tìm đúng Điều 188 nhưng chunk bị cắt ở điểm d (grounding 1).
  4. **q24** (dev, filter Chương III): "Có mấy loại hợp đồng lao động theo luật?"
     - Gold: Điều 20, trang 9–10.
     - Cả 3 chiến lược đều trượt dù top-3 đều thuộc Chương III (B trả về Điều 19, 28, 14).
     - Lỗi này **không** do bị cắt token: evidence nằm ở khoảng token 11, và chunk `art020#k1` của C chứa trọn evidence mà vẫn trượt.
     - Nhiều khả năng do câu hỏi dạng đếm ("có mấy loại") rất ngắn, ít từ trùng với văn bản, và model nhỏ không xếp hạng Điều 20 cao. Filter chương không cứu được vì Chương III có nhiều Điều cùng nói về hợp đồng.

- **Chiến lược được chọn, đánh đổi và điều kiện áp dụng**
  - Chọn **B (`by_article`)** theo tiêu chí đã chốt: Evidence Hit@3 trên dev là B 18/20, C 13/20, A 11/20. Chênh lệch rõ nên không cần dùng tie-break.
  - Trên test, thứ tự Evidence Hit@3 giữ nguyên (B 3/5; A và C 2/5). Nhưng n = 5, test đã bị xem ở v1, và 2/5 câu test (q17, q27) có evidence dài hơn kích thước chunk tối đa của A và C. Vì vậy test **thiên về B** và không đủ để khẳng định thêm.
  - B còn có coherence (2,0) và grounding (1,2) tốt nhất, và index nhanh nhất (10,7 s).
  - Các đánh đổi:
    - Hit@1 trên test của B thấp nhất (1/5). Nếu ứng dụng chỉ đưa top-1 vào LLM thì B không phù hợp.
    - B cần đưa top-3 vào context. Mỗi chunk trung bình 853 ký tự, tối đa 7.248 ký tự, nên prompt dài và tốn token hơn A hoặc C.
  - Điều kiện áp dụng:
    - Văn bản có cấu trúc Điều rõ ràng, và câu hỏi cần trọn một đơn vị pháp lý (điều kiện, ngoại lệ, danh sách).
    - Với Điều dài, cần kỹ thuật bù cho giới hạn 128 token (xem mục cải tiến).

- **Hạn chế về dữ liệu, nhãn, cỡ test, đo thời gian và chi phí**
  - **Test nhỏ** (n = 5): chênh 1 câu tương ứng 20 điểm phần trăm. Tập filter chỉ có n = 4.
  - **Test exposure**: v1 test đã bị xem và nhãn q17, q23, q27 đã sửa (xem mục benchmark).
  - **Nhãn audit**: coherence và grounding là nháp do AI soạn, có một người chấm, chưa có người thứ hai đo độ đồng thuận. Chiến lược cũng không được che (không blind) khi chấm.
  - **Evidence matching strict**: so khớp chuỗi sau chuẩn hóa, nên một chunk diễn đạt tương đương nhưng khác chữ vẫn bị tính là trượt.
  - **Một corpus duy nhất**: kết quả có thể không đúng với văn bản không có cấu trúc Điều/khoản.
  - **Đo thời gian**: chỉ chạy một lần trên CPU của một máy, không lặp lại. A chạy đầu tiên nên thời gian embed có thể gồm cả phần khởi động.
  - **Chi phí 0 USD** chỉ tính phí API, không tính điện năng hay phần cứng.
  - **Metadata**: `page` chỉ là trang bắt đầu; `article_title` bị cắt khi tiêu đề dài hai dòng; còn 1 lỗi chuẩn hóa `choỦy ban`.

- **Nếu làm lại hoặc mở rộng, sẽ cải tiến gì**
  1. **Small-to-big retrieval**: embed từng khoản, mỗi khoản kèm tiêu đề Điều và câu dẫn, nhưng trả về cả Điều. Cách này kết hợp được Hit@1 của C và evidence trọn vẹn của B, sửa được cả q17 và q19.
  2. Dùng **model có cửa sổ dài hơn**, ví dụ họ BGE-M3 hoặc multilingual-E5, rồi so sánh lại với cùng benchmark. Đây là thay đổi model nên phải chạy lại cả A, B và C.
  3. **Hybrid search**, kết hợp BM25 với vector, cho câu chứa thuật ngữ hoặc con số ("05 ngày", "có mấy loại"). Có thể thêm reranker cho top-10.
  4. Với C: **không tách câu dẫn** thành `#preamble`, mà gắn câu dẫn vào đầu mỗi chunk khoản.
  5. Benchmark: tạo **tập test mới chưa từng xem**, khoảng 15–20 câu; có người thứ hai chấm nhãn để đo độ đồng thuận; sửa lỗi `choỦy ban` và lỗi `article_title` hai dòng.

## Sử dụng AI và cách kiểm tra

Công cụ: **Claude Code**, model `claude-opus-5-5`.

| Việc AI hỗ trợ | Cách kiểm tra |
|---|---|
| Viết và sửa code pipeline (`src/`) và script kiểm tra (`scripts/`) | Chạy lại toàn bộ; kiểm tra số dòng trong DB khớp số chunk; [reingest_check.json](../../starter/results/reingest_check.json) PASSED; [evidence_check.json](../../starter/results/evidence_check.json) 25/25; kiểm cả 49 dòng hit nằm trong span của chunk |
| Phát hiện lỗi v1 (A thiếu `article`, evidence không nguyên văn, filter lộ gold) | Đối chiếu với nguồn; số liệu v1 được giữ ở `results/run_v1_before_fix/` để so sánh |
| Kiểm tra metadata | Bộ parse độc lập trong `make_audit_sheets.py`, không dùng lại hàm của chunker; kết quả 45/45 |
| **Soạn nháp nhãn coherence (30) và grounding (15)** | AI đọc từng chunk và ghi lý do cho từng nhãn. Trạng thái trong `labels.json`: `DRAFT_AI`. **Học viên phải đọc lại từng nhãn, sửa nếu không đồng ý, đổi status thành `REVIEWED_BY_STUDENT`, rồi chạy lại `python scripts/score_audit.py`** |
| Soạn nháp báo cáo và experiment log | Mọi số liệu được chép từ `summary.json` và `audit_summary.json`; học viên cần đọc lại và có khả năng giải thích từng kết luận |

Không dùng LLM để chấm tự động (LLM judge), cũng không dùng LLM để sinh câu trả lời trong pipeline.
