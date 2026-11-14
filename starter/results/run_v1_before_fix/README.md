# Run v1 — trước khi sửa (giữ lại để minh bạch)

Kết quả lần chạy đầu tiên (2026-11-14, ~14:23) với benchmark v1. **Không dùng các số này trong báo cáo kết luận**; chúng được giữ lại vì audit sau đó phát hiện 3 lỗi:

1. Chunk chiến lược A không có metadata `article` → Hit@1/Hit@3 của A luôn bằng 0 (lỗi đo, không phải lỗi truy xuất) và câu có filter trả về rỗng.
2. 8/25 `evidence_quote` không có nguyên văn trong nguồn (dấu câu cuối khác, hoặc lược bằng `...`) → Evidence Hit@3 bị tính trượt sai.
3. q23, q25, q27 lọc `{article: <Điều gold>}` → lộ gold source vào filter.

Ngoài ra Hit@1 ở v1 chỉ so số Điều, chưa yêu cầu chứa evidence như GUIDE.

Kết quả test v1 đã được xem trước khi sửa; xem `benchmark/questions.json → revision_history`.
