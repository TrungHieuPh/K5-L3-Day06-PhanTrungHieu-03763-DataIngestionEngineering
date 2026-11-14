# Audit summary — coherence, metadata, grounding

> **Trạng thái nhãn:** DRAFT_AI — nhãn nháp do Claude (claude-opus-5-5) đọc chunk và soạn; sinh viên PHẢI đọc lại từng nhãn, sửa nếu không đồng ý, rồi đổi status thành REVIEWED_BY_STUDENT

## Chunk coherence (10 vị trí × 3 chiến lược, thang 0–2)

| Chiến lược | 0 | 1 | 2 | Trung bình /2 |
|---|---|---|---|---|
| A | 5 | 5 | 0 | 5/20 = 0.5 |
| B | 0 | 0 | 10 | 20/20 = 2.0 |
| C | 1 | 1 | 8 | 17/20 = 1.7 |

| Vị trí | A | B | C |
|---|---|---|---|
| P01 | 1 — Điều 2 trọn vẹn có tiêu đề, nhưng chunk mở đầu bằng mảnh cuối Điều 1 ('người sử dụng lao động trong quan hệ lao động…') và kết thúc ở câu dẫn Điều 3 bị cắt ('…được hiểu như sau'). | 2 — Trọn Điều 2 kèm tiêu đề. | 2 — Điều 2 ngắn nên 1 chunk = trọn Điều, có tiêu đề. |
| P02 | 0 — Vị trí nằm ở tiêu đề Điều 24 'Thử việc'; chunk chỉ có tiêu đề + nửa câu ('…và người lao đ'), đầu chunk cắt giữa từ ('à dẫn đến…'). Chunk overlap kế tiếp p0046 có khoản 1–2 nhưng không phải chunk được chấm theo quy tắc. | 2 — Trọn Điều 24 (3 khoản) kèm tiêu đề. | 2 — Tiêu đề + khoản 1–2 trọn câu; khoản 3 ở chunk khác nhưng không làm mất nghĩa khoản 1–2. |
| P03 | 1 — Có tiêu đề + ý chính khoản 1 Điều 46, nhưng ngoại lệ bị cắt ('…pháp luật về b'), mất ngoại lệ thứ hai (điểm e khoản 1 Điều 36); đầu chunk là mảnh Điều 45. | 2 — Trọn Điều 46. | 2 — Tiêu đề + trọn khoản 1 gồm cả 2 ngoại lệ. |
| P04 | 0 — Câu tại vị trí mất chủ thể: 'ng lao động không được gây khó khăn…' — không rõ là người lao động hay người sử dụng lao động (đảo nghĩa); không có tiêu đề Điều 70; cuối chunk cắt khoản 5. | 2 — Trọn Điều 70 (2.629 ký tự). Văn bản mạch lạc, nhưng lưu ý: embedding chỉ đọc ~128 token đầu nên phần khoản 4 không được mã hóa. | 2 — Khoản 4 trọn vẹn, tự nêu rõ chủ đề 'thương lượng tập thể' và chủ thể; thiếu tiêu đề Điều nhưng không làm mất nghĩa. |
| P05 | 0 — Vị trí ở tiêu đề Điều 99; chunk chỉ có tiêu đề + câu dẫn + '1. Nếu do lỗi của' rồi cắt — không có trường hợp nào trọn; phần đầu là khoản 3–4 Điều 98 ('khoản 1 và khoản 2 Điều này' không rõ Điều nào). | 2 — Trọn Điều 99 (3 khoản, điểm a–b). | 2 — Tiêu đề + câu dẫn + khoản 1 trọn câu (204 ký tự); khoản 2–3 ở chunk khác. |
| P06 | 1 — Khoản 4 Điều 125 trọn câu nhưng không có tiêu đề/câu dẫn 'sa thải' nên không rõ hệ quả; câu định nghĩa 'lý do chính đáng' bị cắt ('Trường hợp được c'); đầu chunk là mảnh khoản 2. | 2 — Trọn Điều 125 kèm tiêu đề 'Áp dụng hình thức xử lý kỷ luật sa thải'. | 1 — Khoản 4 trọn cả định nghĩa lý do chính đáng, nhưng thiếu câu dẫn/tiêu đề nên chunk không nói hành vi này dẫn tới sa thải. |
| P07 | 1 — Khoản 2 Điều 151 trọn vẹn, nhưng chunk mở đầu bằng mảnh điểm d khoản 1 và kết thúc cắt giữa khoản 3 ('…và đư'). | 2 — Trọn Điều 151. | 2 — Khoản 2 tự đủ nghĩa (chủ thể 'người lao động nước ngoài', thời hạn HĐLĐ). |
| P08 | 0 — Mất chủ thể định nghĩa: chunk bắt đầu 'tổ chức đại diện người lao động với người sử dụng lao động…phát sinh trong trường hợp sau đây:' — không biết danh sách a)–c) là của 'tranh chấp lao động tập thể về quyền'; điểm c cắt giữa câu. | 2 — Trọn Điều 179. | 2 — Khoản 2 gồm câu định nghĩa + điểm a–c trọn vẹn. |
| P09 | 1 — Còn cụm 'đình công trong trường hợp sau đây:' nên hiểu đây là trường hợp được đình công, nhưng mất chủ thể có quyền (tổ chức đại diện NLĐ); cuối chunk là tiêu đề Điều 200 + nửa câu. | 2 — Trọn Điều 199 kèm câu dẫn. | 0 — Câu dẫn (≥200 ký tự) bị tách thành chunk #preamble riêng; chunk k1-2 chỉ còn 2 điều kiện, không có chủ thể và không có vị ngữ 'có quyền đình công' — đọc riêng không biết đây là điều kiện của việc gì. |
| P10 | 0 — Khoản 2 Điều 220 mất chủ thể ('bảo đảm cho người lao động có quyền…' — thiếu 'hợp đồng lao động, thỏa ước… đã giao kết có nội dung không trái hoặc'); khoản 3 cắt giữa câu. | 2 — Trọn Điều 220 (kèm dòng thông qua và chữ ký ở cuối — nhiễu nhỏ, không ảnh hưởng nghĩa). | 2 — Tiêu đề + khoản 1–2 trọn vẹn. |

## Metadata usefulness (5 câu test × top-3)

| Chiến lược | Đủ & đúng / đã kiểm | Lỗi | Filter compliance (test) | Filter compliance (cả bộ) |
|---|---|---|---|---|
| A | 15/15 | — | 2/2 | 4/4 |
| B | 15/15 | — | 2/2 | 4/4 |
| C | 15/15 | — | 2/2 | 4/4 |

Filter ablation (4 câu có filter, cùng index, bỏ filter):

| Chiến lược | Evidence Hit@3 có filter | Evidence Hit@3 không filter | Chunk ngoài phạm vi khi bỏ filter |
|---|---|---|---|
| A | 1/4 | 1/4 | 4/12 |
| B | 3/4 | 2/4 | 2/12 |
| C | 1/4 | 1/4 | 1/12 |

Chunk A vắt qua ranh giới chương: 16/421.

- 45/45 bản ghi (5 câu test × top-3 × 3 chiến lược) khớp bộ kiểm tra độc lập (regex riêng cho 'Điều N.'/'Chương X', vị trí văn bản trong nguồn → trang). Đối chiếu bằng mắt các bản ghi trong grounding_sample.md: số Điều, trang và chương khớp nội dung chunk. Sinh viên nên mở PDF đối chiếu tối thiểu 5 bản ghi (ví dụ q19-A rank1 trang 52, q27-B rank2 trang 77–78).
- Hạn chế A: chunk vắt nhiều Điều chỉ có một giá trị `article`/`chapter_roman` (Điều chứa đầu cửa sổ); danh sách đầy đủ nằm ở `articles`. Filter chương dùng chương chính nên chunk vắt ranh giới chương có thể bị loại/nhận sai.
- Hạn chế chung: cột `page` = trang bắt đầu; chunk vắt trang cần `page_end` trong metadata JSON để truy đủ.
- Lỗi văn bản (không phải metadata) quan sát được: B art186 dính tiêu đề 'Mục 2 THẨM QUYỀN VÀ TRÌNH TỰ…' của mục kế tiếp; C art042#k5-6 có lỗi ghép từ 'choỦy ban' từ bước chuẩn hóa.

## Grounding (5 câu test, top-3 gộp, thang 0–2)

| Chiến lược | 0 | 1 | 2 | Trung bình /2 | Proxy Evidence Hit@3 (test) |
|---|---|---|---|---|---|
| A | 2 | 2 | 1 | 4/10 = 0.8 | 2/5 |
| B | 2 | 0 | 3 | 6/10 = 1.2 | 3/5 |
| C | 3 | 1 | 1 | 3/10 = 0.6 | 2/5 |

| Câu | A | B | C |
|---|---|---|---|
| q06 | 2 — Rank 1 có tiêu đề Điều 220 + khoản 1 'có hiệu lực thi hành từ ngày 01 tháng 01 năm 2021'; truy được Điều 220, trang 92–93. | 2 — Rank 1 = trọn Điều 220. | 2 — Rank 1 = Điều 220 khoản 1–2. |
| q17 | 0 — Không chunk nào chứa khoản 2 Điều 35. Rank 2 chỉ có tiêu đề Điều 35 + đầu khoản 1 (trường hợp PHẢI báo trước) — ngược với câu hỏi. | 0 — Top-3 là Điều 45, 37, 38; không có Điều 35. | 0 — Top-3 là Điều 45 k2, Điều 40, Điều 36 k3. Rank 3 nói NSDLĐ không phải báo trước — dễ gây nhầm chủ thể. |
| q19 | 1 — Rank 1 có trọn câu số ngày (05/30, 20/365) nhưng không có tiêu đề/câu dẫn nói đây là căn cứ sa thải (chỉ suy ra qua metadata Điều 125); câu định nghĩa lý do chính đáng bị cắt. | 0 — Top-3 là Điều 47, 101, 126; Điều 125 không lọt top-3. | 1 — Rank 1 = khoản 4 Điều 125 trọn câu + định nghĩa lý do chính đáng, nhưng thiếu câu dẫn 'hình thức sa thải được áp dụng trong trường hợp sau' nên chunk không tự xác nhận hệ quả sa thải. |
| q23 | 0 — Top-3 là Điều 122 (2 chunk) và Điều 127–128; không có nội dung Điều 125 về quấy rối tình dục → sa thải. | 2 — Rank 3 = trọn Điều 125 có tiêu đề 'sa thải' + khoản 2 nêu 'quấy rối tình dục tại nơi làm việc được quy định trong nội quy lao động'; truy được Điều 125, trang 52. | 0 — Top-3 là Điều 122 k2-3, 127 k3, 118; không có Điều 125. |
| q27 | 1 — Rank 3 (Điều 188 khoản 1) chỉ có câu dẫn + điểm a, b, c rồi cắt ở 'd) V' — thiếu d, đ, e (3/6 loại tranh chấp). | 2 — Rank 2 = trọn Điều 188, đủ 6 điểm a–e. | 0 — Top-3 là Điều 193 k4, 193 k6, 189 k5; không có Điều 188. |
