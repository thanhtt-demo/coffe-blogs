# Kế hoạch Triển khai: Pipeline Content Quality

## Tổng quan

Triển khai cải thiện chất lượng nội dung cho pipeline tạo bài blog tự động, can thiệp vào 4 node: Extract (lọc relevance), Outline (thesis), Draft (thesis prompt + lọc references), Review (2 tiêu chí mới). Thêm `hypothesis` vào dev dependencies để viết property-based tests.

## Tasks

- [x] 1. Thêm `hypothesis` vào dev dependencies và tạo file test
  - Thêm `hypothesis>=6.100.0` vào `[project.optional-dependencies] dev` trong `pipeline/pyproject.toml`
  - Tạo file `pipeline/tests/test_content_quality.py` với import cơ bản
  - _Requirements: Chiến lược Testing trong design_

- [x] 2. Extract Node — LLM-based relevance filter
  - [x] 2.1 Implement hàm `_filter_irrelevant_academic(items, topic)` trong `pipeline/src/coffee_pipeline/nodes/extract.py`
    - Thêm import `call_llm` từ `..llm`
    - Tạo system prompt cho relevance classifier (chỉ giữ papers liên quan đến chủ đề cà phê đang viết)
    - Gom tất cả academic items vào 1 batch prompt, gọi LLM 1 lần duy nhất
    - Parse JSON array indices từ LLM response, giữ lại items có index trong kết quả
    - Fallback: nếu LLM call fail hoặc JSON parse fail → giữ tất cả items, ghi log warning
    - Bỏ qua index ngoài range
    - Skip LLM call khi `PIPELINE_DRY_RUN` hoặc không có academic items
    - Ghi log mỗi tài liệu bị loại và tổng kết kept/total
    - _Requirements: 3.1, 3.2, 3.3, 3.4_
  - [x] 2.2 Tích hợp `_filter_irrelevant_academic()` vào `extract_node()`
    - Tách academic items (`arxiv`, `semantic_scholar`, `openalex`) ra khỏi `search_results` trước khi trích xuất
    - Gọi `_filter_irrelevant_academic()` trên batch academic items
    - Chỉ trích xuất nội dung cho các items đã qua lọc
    - Web và YouTube sources đi qua không bị lọc
    - _Requirements: 3.1, 3.2, 3.3_
  - [ ]* 2.3 Write property test cho LLM relevance filter fallback safety
    - **Property 4: LLM relevance filter — fallback safety**
    - Mock `call_llm` để raise exception, verify hàm trả về toàn bộ items gốc
    - **Validates: Requirements 3.4**
  - [ ]* 2.4 Write unit tests cho Extract Node LLM filter
    - Test fallback khi LLM call fail (mock exception) → giữ tất cả items, ghi log warning
    - Test ghi log kept/total khi LLM trả về kết quả hợp lệ
    - Test skip LLM call khi không có academic items
    - _Requirements: 3.2, 3.3, 3.4_

- [x] 3. Outline Node — Thêm trường thesis
  - [x] 3.1 Cập nhật `_SYSTEM_PROMPT` trong `pipeline/src/coffee_pipeline/nodes/outline.py`
    - Thêm trường `thesis` vào JSON schema mẫu trong prompt
    - Thêm rule: "Mỗi section PHẢI có một `thesis` riêng biệt — luận điểm chính duy nhất, tối đa 1 câu"
    - Thêm rule: "KHÔNG section nào được lặp lại luận điểm của section khác. Nếu hai section có thesis giống nhau, hãy gộp chúng lại."
    - _Requirements: 1.1, 1.2_
  - [ ]* 3.2 Write property test cho outline thesis
    - **Property 1: Outline sections luôn có thesis**
    - Generate random outline sections, verify mỗi section có trường `thesis` không rỗng
    - **Validates: Requirements 1.1**
  - [ ]* 3.3 Write unit test kiểm tra prompt chứa thesis rule
    - Kiểm tra `_SYSTEM_PROMPT` chứa từ khóa "thesis" và quy tắc uniqueness
    - _Requirements: 1.2_

- [x] 4. Checkpoint — Đảm bảo tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 5. Draft Node — Thesis-aware prompt và post-draft reference filter
  - [x] 5.1 Cập nhật `draft_node()` để đưa thesis vào prompt trong `pipeline/src/coffee_pipeline/nodes/draft.py`
    - Trong vòng lặp build `sections_lines`, thêm thesis từ `sec.get("thesis", "")` vào mỗi section
    - Thêm chỉ dẫn vào `user_message`: mỗi section CHỈ viết quanh thesis đã gán, không lặp dữ kiện đã xuất hiện ở section trước
    - _Requirements: 1.3, 1.4_
  - [x] 5.2 Implement hàm `_filter_references_llm(draft_text, docs, topic)` trong `draft.py`
    - Gom danh sách extracted docs (title + URL) và nội dung draft vào 1 prompt
    - Gọi LLM 1 lần để đánh giá từng doc có liên quan đến nội dung draft hay không
    - LLM trả về JSON array chứa index của các docs LIÊN QUAN
    - Loại bỏ docs không liên quan, giữ tất cả docs liên quan (không hardcode max)
    - Fallback: nếu LLM call fail → giữ tất cả docs, ghi log warning
    - `temperature=0.0`, `max_tokens=512`
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 5.3 Tích hợp `_filter_references_llm()` vào `draft_node()` — gọi SAU khi `call_llm()` trả về draft
    - Parse references YAML block trong draft, thay thế bằng references đã lọc qua LLM
    - Nếu không tìm thấy references block → giữ nguyên draft
    - _Requirements: 2.4_
  - [ ]* 5.4 Write property test cho reference filter
    - **Property 3: Reference filter LLM — fallback safety**
    - Mock `call_llm` để raise exception, verify hàm trả về toàn bộ docs gốc
    - **Validates: Requirements 2.1, 2.2, 2.3**
  - [ ]* 5.5 Write property test cho draft prompt chứa thesis
    - **Property 2: Draft prompt chứa tất cả thesis từ outline**
    - Generate random outlines với thesis, build prompt, verify tất cả thesis xuất hiện trong prompt
    - **Validates: Requirements 1.3**
  - [ ]* 5.6 Write unit tests cho Draft Node
    - Test reference filter chạy sau LLM (mock `call_llm`, verify `_filter_references` được gọi trên output)
    - Test draft prompt chứa no-repeat instruction
    - _Requirements: 1.4, 2.4_

- [x] 6. Review Node — Thêm 2 tiêu chí đánh giá mới
  - [x] 6.1 Cập nhật `user_message` trong `review_node()` tại `pipeline/src/coffee_pipeline/nodes/review.py`
    - Thêm tiêu chí 5: "Cross-Section Repetition" (0-10) — kiểm tra lặp luận điểm/dữ kiện giữa các section
    - Thêm tiêu chí 6: "Reference Alignment" (0-10) — kiểm tra khớp references với nội dung
    - Cập nhật JSON output schema thêm `repetition_score` và `reference_alignment_score`
    - Cập nhật tính điểm: "Score tổng = trung bình 6 tiêu chí"
    - _Requirements: 4.1, 4.2, 4.3, 5.1, 5.2, 5.3, 5.4_
  - [x] 6.2 Cập nhật log output trong `review_node()` để in thêm Repetition và RefAlign scores
    - _Requirements: 4.1, 5.1_
  - [ ]* 6.3 Write unit tests cho Review Node
    - Test prompt chứa "Cross-Section Repetition" và "Reference Alignment"
    - Test prompt yêu cầu trung bình 6 tiêu chí
    - Test ResearchState tương thích với outline có thesis và review có 6 scores
    - _Requirements: 4.1, 4.3, 5.1, 5.4, 6.1, 6.2_

- [x] 7. Final checkpoint — Đảm bảo tất cả tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Ghi chú

- Tasks đánh dấu `*` là optional, có thể bỏ qua để triển khai nhanh hơn
- Mỗi task tham chiếu requirements cụ thể để đảm bảo traceability
- Checkpoints đảm bảo kiểm tra chất lượng tăng dần
- Property tests kiểm tra tính đúng đắn phổ quát, unit tests kiểm tra ví dụ cụ thể và edge cases
