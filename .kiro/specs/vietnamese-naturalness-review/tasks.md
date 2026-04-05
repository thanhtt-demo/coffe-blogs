# Kế hoạch triển khai: Vietnamese Naturalness Review

## Tổng quan

Thay thế review node scoring-based hiện tại bằng kiến trúc review + rewrite tuyến tính. Cập nhật ResearchState, viết lại review.py, tạo rewrite.py mới, cập nhật graph.py, dọn dẹp draft.py, và cập nhật tests.

## Tasks

- [x] 1. Cập nhật ResearchState và fixtures
  - [x] 1.1 Cập nhật `pipeline/src/coffee_pipeline/state.py`
    - Bỏ 3 trường: `review_score`, `review_passed`, `revision_count`
    - Chuyển `review_feedback` thành `NotRequired[str]`
    - Thêm `draft_post_original: NotRequired[str]`
    - _Requirements: 6.1, 6.2, 6.3_

  - [x] 1.2 Cập nhật `pipeline/tests/conftest.py`
    - Bỏ `review_score`, `review_passed`, `revision_count` khỏi `sample_state`
    - _Requirements: 6.4_

- [x] 2. Viết lại Review Node
  - [x] 2.1 Viết lại `pipeline/src/coffee_pipeline/nodes/review.py`
    - Thay thế hoàn toàn nội dung hiện tại
    - System prompt bao gồm 7 khía cạnh đánh giá (factual, tone, concision, formatting, repetition, references, Vietnamese naturalness)
    - Output là JSON `{"issues": [{"original": str, "category": str, "suggestion": str}]}`
    - Không scoring, không pass/fail, không revision_count
    - Xử lý lỗi: JSON parse fail → lưu raw text; LLM fail → feedback rỗng; DRY_RUN → feedback rỗng
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 2.1, 2.2, 2.3_

  - [ ]* 2.2 Viết property test — Property 1: Review output có cấu trúc hợp lệ
    - **Property 1: Review output có cấu trúc hợp lệ**
    - Generator: tạo random JSON `{"issues": [...]}` với 0-10 issues
    - Mock `call_llm` trả về JSON string đã generate
    - Assert: mỗi issue có đủ `original`, `category`, `suggestion`
    - **Validates: Requirements 1.3, 2.1**

  - [ ]* 2.3 Viết property test — Property 2: Review output không chứa scoring
    - **Property 2: Review output không chứa scoring**
    - Generator: tạo random `draft_post` và `topic`
    - Mock `call_llm` trả về valid JSON issues
    - Assert: output dict không chứa keys `review_score`, `review_passed`, `revision_count`
    - **Validates: Requirements 1.4**

  - [ ]* 2.4 Viết property test — Property 3: Review fallback khi JSON không hợp lệ
    - **Property 3: Review fallback khi JSON không hợp lệ**
    - Generator: tạo random strings không phải JSON hợp lệ
    - Mock `call_llm` trả về string đã generate
    - Assert: không raise exception, `review_feedback` chứa raw text
    - **Validates: Requirements 2.2**

  - [ ]* 2.5 Viết unit tests cho Review Node
    - Test dry-run: set `PIPELINE_DRY_RUN`, verify feedback rỗng, không gọi LLM
    - Test LLM exception: mock `call_llm` raise exception, verify feedback rỗng
    - _Requirements: 1.5, 2.3_

- [x] 3. Checkpoint — Đảm bảo tất cả tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Tạo Rewrite Node
  - [x] 4.1 Tạo file `pipeline/src/coffee_pipeline/nodes/rewrite.py`
    - Hàm `rewrite_node(state)` nhận `draft_post` và `review_feedback`
    - Sao chép `draft_post` → `draft_post_original`, thêm "[DRAFT] " vào title trong frontmatter
    - Parse `review_feedback` JSON → danh sách issues
    - Nếu feedback rỗng hoặc `{"issues": []}` → trả về draft nguyên bản + `draft_post_original`, không gọi LLM
    - Gọi LLM với system prompt yêu cầu targeted replacements, giữ nguyên frontmatter/headings/images
    - Xử lý lỗi: JSON parse fail → dùng raw text; LLM fail → giữ nguyên draft; DRY_RUN → skip LLM
    - Output: `{"draft_post": str, "draft_post_original": str}`
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 4.1, 4.2, 4.3, 4.4_

  - [ ]* 4.2 Viết property test — Property 5: Rewrite với feedback rỗng giữ nguyên bài viết
    - **Property 5: Rewrite với feedback rỗng giữ nguyên bài viết**
    - Generator: tạo random `draft_post` có frontmatter
    - Input: `review_feedback` là `""` hoặc `'{"issues": []}'`
    - Assert: output `draft_post` === input `draft_post`, không gọi `call_llm`
    - **Validates: Requirements 4.4**

  - [ ]* 4.3 Viết property test — Property 6: Rewrite tạo draft_post_original với title "[DRAFT] "
    - **Property 6: Rewrite tạo draft_post_original với title "[DRAFT] " và draft_post giữ title gốc**
    - Generator: tạo random `draft_post` có YAML frontmatter chứa `title`
    - Generator: tạo random review issues (có thể rỗng hoặc có issues)
    - Mock `call_llm` trả về bài viết đã sửa (giữ nguyên title gốc)
    - Assert: (a) `draft_post_original` tồn tại, (b) title trong `draft_post_original` bắt đầu bằng `[DRAFT] `, (c) title trong `draft_post` KHÔNG bắt đầu bằng `[DRAFT] `
    - **Validates: Requirements 3.5, 3.6, 3.7**

  - [ ]* 4.4 Viết property test — Property 4: Rewrite bảo toàn cấu trúc bài viết
    - **Property 4: Rewrite bảo toàn cấu trúc bài viết**
    - Generator: tạo random draft có frontmatter, headings, images
    - Generator: tạo random review issues
    - Mock `call_llm` trả về bài viết đã sửa (giữ nguyên structure)
    - Assert: frontmatter, headings, image URLs trước/sau giống nhau
    - **Validates: Requirements 4.1, 4.2, 4.3**

  - [ ]* 4.5 Viết unit tests cho Rewrite Node
    - Test dry-run: set `PIPELINE_DRY_RUN`, verify draft unchanged, verify `draft_post_original` có title "[DRAFT] "
    - Test LLM exception: mock `call_llm` raise exception, verify draft giữ nguyên, `draft_post_original` vẫn có "[DRAFT] "
    - _Requirements: 3.4, 3.5, 3.6_

- [x] 5. Checkpoint — Đảm bảo tất cả tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 6. Cập nhật Graph và dọn dẹp Draft Node
  - [x] 6.1 Cập nhật `pipeline/src/coffee_pipeline/graph.py`
    - Import `rewrite_node` từ `nodes.rewrite`
    - Thêm node `"rewrite"` vào graph
    - Thay conditional edge `review → {draft, END}` bằng linear edges: `review → rewrite`, `rewrite → END`
    - Xóa hàm `_review_decision()`
    - _Requirements: 5.1, 5.2, 5.3, 5.4, 5.5_

  - [x] 6.2 Dọn dẹp `pipeline/src/coffee_pipeline/nodes/draft.py`
    - Bỏ đọc `review_feedback` và `revision_count` từ state
    - Bỏ biến `revision_note` và logic tạo revision feedback block
    - Bỏ `revision #{revision_count + 1}` trong log message
    - _Requirements: 6.4_

  - [x] 6.3 Cập nhật `pipeline/tests/test_tools.py`
    - Xóa 3 tests liên quan đến `_review_decision` (đã bị xóa khỏi graph.py)
    - _Requirements: 5.1_

  - [ ]* 6.4 Viết unit tests cho graph topology và state structure
    - Test graph topology: verify edges `draft→review→rewrite→END`, không có conditional edge
    - Test state structure: verify `ResearchState` annotations không chứa `review_score`, `review_passed`, `revision_count`; có chứa `review_feedback` và `draft_post_original`
    - Test draft node cleanup: verify `draft_node` không reference `revision_count` hoặc `review_feedback` từ state
    - _Requirements: 5.5, 6.1, 6.2, 6.3_

- [x] 7. Checkpoint cuối — Đảm bảo tất cả tests pass
  - Ensure all tests pass, ask the user if questions arise.

- [x] 8. Cập nhật CLI — export 2 file riêng biệt
  - [x] 8.1 Cập nhật `initial_state` trong lệnh `research` (`pipeline/src/coffee_pipeline/cli.py`)
    - Bỏ `review_score`, `review_passed`, `revision_count` khỏi `initial_state` dict
    - _Requirements: 7.8_

  - [x] 8.2 Export `draft_post_original` thành file `-draft.md`
    - Sau khi export `draft_post` thành file chính, lấy `draft_post_original` từ `final_state`
    - Nếu tồn tại và non-empty: strip code fence, localize images, write file `{slug}-draft.md`, format với prettier
    - Nếu không tồn tại: bỏ qua, chỉ export file chính
    - _Requirements: 7.1, 7.2, 7.3, 7.5_

  - [x] 8.3 Cập nhật summary output và log
    - Bỏ hiển thị `Score` và `Revisions` (do đã bỏ scoring)
    - Thêm hiển thị đường dẫn file draft original nếu có
    - Log đường dẫn cả 2 file đã export
    - _Requirements: 7.4, 7.7_

  - [x] 8.4 Cập nhật `_save_pipeline_cache` để lưu `draft_post_original`
    - Lưu `draft_post_original` thành `draft-original.md` trong cache dir
    - _Requirements: 7.6_

  - [ ]* 8.5 Viết property test — Property 7: CLI export 2 file khi draft_post_original tồn tại
    - **Property 7: CLI export 2 file khi draft_post_original tồn tại**
    - Generator: tạo random `draft_post` và `draft_post_original` có YAML frontmatter hợp lệ
    - Mock `graph.invoke` trả về final_state chứa cả 2 trường
    - Assert: (a) file `{slug}.md` được tạo, (b) file `{slug}-draft.md` được tạo
    - Variant: khi `draft_post_original` rỗng → chỉ tạo file chính
    - **Validates: Requirements 7.1, 7.2, 7.5**

  - [ ]* 8.6 Viết unit tests cho CLI dual export
    - Test dual export: mock graph.invoke trả về cả `draft_post` và `draft_post_original`, verify 2 file
    - Test single export: mock graph.invoke không có `draft_post_original`, verify chỉ 1 file
    - Test summary không có scoring: verify output không chứa `Score` hay `Revisions`
    - Test cache lưu `draft-original.md`: verify `_save_pipeline_cache` lưu đúng
    - _Requirements: 7.1, 7.2, 7.4, 7.5, 7.6, 7.7_

- [x] 9. Checkpoint cuối — Đảm bảo tất cả tests pass
  - Ensure all tests pass, ask the user if questions arise.

## Ghi chú

- Tasks đánh dấu `*` là optional, có thể bỏ qua để triển khai nhanh hơn
- Mỗi task tham chiếu requirements cụ thể để đảm bảo traceability
- Checkpoints đảm bảo kiểm tra incremental sau mỗi giai đoạn
- Property tests validate correctness properties từ design document
- Unit tests validate edge cases và error handling cụ thể
