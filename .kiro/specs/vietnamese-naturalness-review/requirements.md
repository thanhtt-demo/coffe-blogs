# Requirements Document

## Giới thiệu

Pipeline tạo bài blog tự động cho "Ba Tê và Cà Phê" hiện có review node đánh giá chất lượng nội dung theo 6 tiêu chí scoring (0-10). Tuy nhiên, hệ thống scoring và vòng lặp review ⟲ draft phức tạp mà không mang lại giá trị tương xứng. Bài viết output vẫn thường mang cảm giác "văn dịch" — cụm từ thụ động không tự nhiên, thuật ngữ dịch sát tiếng Anh, câu cứng thiếu tính miêu tả.

Feature này thay thế review node hiện tại bằng một review node mới (gộp cả đánh giá chất lượng nội dung lẫn đánh giá sự tự nhiên tiếng Việt), và thêm rewrite node để sửa bài dựa trên feedback. Bỏ hoàn toàn hệ thống scoring và vòng lặp review ⟲ draft.

Pipeline flow mới:
```
query_gen → research → extract → outline → image_fetch → draft → review → rewrite → END
```

Thay đổi so với pipeline hiện tại:
- **Bỏ**: scoring 0-10 per criteria, pass/fail threshold, vòng lặp review ⟲ draft
- **Gộp**: review node cũ (6 tiêu chí) + naturalness review → 1 review node duy nhất
- **Thêm**: rewrite node nhận feedback và sửa bài
- **Flow**: thẳng từ draft → review → rewrite → END (không loop)

## Glossary

- **Pipeline**: Hệ thống LangGraph tự động tạo bài blog, gồm các node nối tiếp nhau
- **Review_Node**: Node mới (thay thế review node cũ) dùng LLM để đánh giá toàn diện bài viết — bao gồm cả chất lượng nội dung và sự tự nhiên tiếng Việt — output là danh sách vấn đề cụ thể kèm gợi ý sửa (file `review.py`)
- **Rewrite_Node**: Node mới dùng LLM để sửa bài viết dựa trên feedback từ Review_Node, chỉ sửa targeted thay vì viết lại toàn bộ (file `rewrite.py`)
- **Draft_Post**: Bài viết dạng Markdown (có YAML frontmatter) được lưu trong state field `draft_post`
- **Draft_Post_Original**: Bản sao của `draft_post` trước khi rewrite, với title có tiền tố "[DRAFT] " trong YAML frontmatter, lưu trong state field `draft_post_original` — cho phép user so sánh bản nháp gốc và bản đã sửa
- **Review_Feedback**: Danh sách các vấn đề cần sửa kèm gợi ý cụ thể, lưu trong state field `review_feedback`
- **ResearchState**: TypedDict định nghĩa state của pipeline (file `state.py`)
- **Văn_Dịch**: Lối viết tiếng Việt mang cảm giác dịch từ tiếng Anh — cấu trúc câu thụ động, từ vựng không quen thuộc với người Việt, thiếu tính miêu tả cảm giác
- **Cupping**: Quy trình thử nếm cà phê chuyên nghiệp, có bộ thuật ngữ riêng cần được Việt hóa phù hợp
- **Actionable_Feedback**: Feedback dạng cụ thể, chỉ rõ đoạn nào cần sửa và gợi ý sửa thế nào, thay vì chỉ cho điểm chung chung

## Requirements

### Requirement 1: Review Node mới — Gộp đánh giá chất lượng nội dung và sự tự nhiên tiếng Việt

**User Story:** Là người vận hành pipeline, tôi muốn có một review node duy nhất đánh giá toàn diện bài viết (cả nội dung lẫn ngôn ngữ), output là danh sách vấn đề cụ thể cần sửa thay vì điểm số, để feedback có thể được áp dụng trực tiếp vào bước rewrite.

#### Acceptance Criteria

1. WHEN Draft_Node hoàn tất, THE Pipeline SHALL chuyển bài viết sang Review_Node (thay thế review node cũ).
2. WHEN Review_Node nhận bài viết, THE Review_Node SHALL gọi LLM để phân tích bài viết theo các khía cạnh sau và trả về danh sách vấn đề cụ thể cần sửa:
   - Factual accuracy: dữ kiện cà phê sai, số liệu không chính xác, tên giống/quy trình sai
   - Tone & style: câu sáo rỗng kiểu AI, thiếu personality, dùng ẩn dụ/thuật ngữ IT
   - Concision: đoạn lặp ý, câu đệm không thêm thông tin mới, giải thích rườm rà
   - Formatting: lỗi YAML frontmatter, markdown structure không hợp lý
   - Cross-section repetition: luận điểm hoặc dữ kiện xuất hiện ở nhiều section
   - Reference alignment: reference không liên quan đến nội dung, hoặc nguồn được nhắc đến nhưng thiếu trong references
   - Sự tự nhiên tiếng Việt: cụm từ thụ động không tự nhiên, từ dịch sát tiếng Anh, thuật ngữ chuyên ngành dịch thô chưa Việt hóa, từ ngữ lạc ngữ cảnh cà phê, câu cứng thiếu tính miêu tả cảm giác
3. WHEN Review_Node hoàn tất phân tích, THE Review_Node SHALL trả về danh sách feedback dạng có cấu trúc, mỗi mục gồm: đoạn văn gốc có vấn đề, loại vấn đề (category), và gợi ý sửa cụ thể.
4. THE Review_Node SHALL KHÔNG cho điểm (không scoring 0-10, không pass/fail threshold).
5. WHEN biến môi trường PIPELINE_DRY_RUN được bật, THE Review_Node SHALL bỏ qua LLM call và trả về feedback rỗng.

### Requirement 2: Review Node — Output format có cấu trúc

**User Story:** Là người vận hành pipeline, tôi muốn output của Review_Node có format JSON có cấu trúc, để Rewrite_Node có thể parse và áp dụng từng gợi ý sửa một cách chính xác.

#### Acceptance Criteria

1. THE Review_Node SHALL yêu cầu LLM trả về JSON với cấu trúc gồm: danh sách các issue, mỗi issue chứa trường `original` (đoạn văn gốc có vấn đề), `category` (loại vấn đề), và `suggestion` (gợi ý sửa cụ thể).
2. WHEN LLM trả về JSON không hợp lệ, THE Review_Node SHALL fallback bằng cách lưu toàn bộ raw text response làm review_feedback và ghi log warning.
3. WHEN LLM call bị lỗi (network, timeout), THE Review_Node SHALL lưu feedback rỗng vào state và ghi log warning, cho phép Rewrite_Node bỏ qua bước sửa bài.

### Requirement 3: Rewrite Node — Sửa bài viết dựa trên review feedback

**User Story:** Là người vận hành pipeline, tôi muốn có một node tự động sửa bài viết dựa trên feedback từ review, để bài viết output chất lượng hơn mà không cần chỉnh sửa thủ công.

#### Acceptance Criteria

1. WHEN Review_Node trả về feedback, THE Rewrite_Node SHALL nhận bài viết gốc (draft_post) và toàn bộ review feedback làm input.
2. WHEN Rewrite_Node gọi LLM, THE Rewrite_Node SHALL yêu cầu LLM thực hiện targeted replacements dựa trên từng issue trong feedback, thay vì viết lại toàn bộ bài viết.
3. WHEN Rewrite_Node hoàn tất, THE Rewrite_Node SHALL cập nhật state field `draft_post` bằng bài viết đã sửa.
4. WHEN biến môi trường PIPELINE_DRY_RUN được bật, THE Rewrite_Node SHALL bỏ qua LLM call và giữ nguyên draft_post hiện tại.
5. WHEN Rewrite_Node bắt đầu xử lý (trước khi gọi LLM), THE Rewrite_Node SHALL sao chép `draft_post` hiện tại vào state field `draft_post_original` để lưu bản gốc trước khi sửa.
6. WHEN Rewrite_Node lưu bản gốc vào `draft_post_original`, THE Rewrite_Node SHALL thêm tiền tố "[DRAFT] " vào giá trị `title` trong YAML frontmatter của `draft_post_original` để phân biệt bản nháp với bản đã sửa.
7. WHEN Rewrite_Node hoàn tất, THE `draft_post` (bài viết đã sửa) SHALL giữ nguyên title gốc (KHÔNG có tiền tố "[DRAFT] ").

### Requirement 4: Rewrite Node — Bảo toàn cấu trúc bài viết

**User Story:** Là người vận hành pipeline, tôi muốn Rewrite_Node chỉ sửa ngôn ngữ và nội dung theo feedback mà không thay đổi cấu trúc bài viết, để bài viết sau khi rewrite vẫn giữ nguyên frontmatter, heading, hình ảnh và references.

#### Acceptance Criteria

1. WHEN Rewrite_Node sửa bài viết, THE Rewrite_Node SHALL giữ nguyên toàn bộ YAML frontmatter (publishDate, title, excerpt, image, category, tags, author, references).
2. WHEN Rewrite_Node sửa bài viết, THE Rewrite_Node SHALL giữ nguyên tất cả heading (##, ###) và thứ tự các section.
3. WHEN Rewrite_Node sửa bài viết, THE Rewrite_Node SHALL giữ nguyên tất cả hình ảnh (URL, alt text) và vị trí chèn hình ảnh.
4. WHEN review_feedback rỗng hoặc không có issue nào, THE Rewrite_Node SHALL giữ nguyên draft_post mà không gọi LLM.

### Requirement 5: Cập nhật pipeline flow — bỏ vòng lặp, thêm rewrite

**User Story:** Là developer bảo trì pipeline, tôi muốn pipeline flow được cập nhật để bỏ vòng lặp review ⟲ draft và thêm rewrite node, để luồng xử lý đơn giản và hiệu quả hơn.

#### Acceptance Criteria

1. THE Pipeline SHALL bỏ vòng lặp review ⟲ draft hiện tại (bỏ conditional edge từ review quay lại draft).
2. WHEN Draft_Node hoàn tất, THE Pipeline SHALL chuyển sang Review_Node.
3. WHEN Review_Node hoàn tất, THE Pipeline SHALL chuyển sang Rewrite_Node.
4. WHEN Rewrite_Node hoàn tất, THE Pipeline SHALL kết thúc (END).
5. THE Pipeline flow hoàn chỉnh SHALL là: query_gen → research → extract → outline → image_fetch → draft → review → rewrite → END.

### Requirement 6: Cập nhật ResearchState — bỏ trường scoring, thêm trường mới

**User Story:** Là developer bảo trì pipeline, tôi muốn ResearchState được cập nhật để phản ánh việc bỏ scoring và thêm rewrite node, để type checking hoạt động chính xác.

#### Acceptance Criteria

1. THE ResearchState SHALL bỏ các trường liên quan đến scoring: `review_score` (float), `review_passed` (bool), `revision_count` (int).
2. THE ResearchState SHALL giữ trường `review_feedback` (str) để lưu feedback dạng JSON string từ Review_Node.
3. THE ResearchState SHALL thêm trường `draft_post_original` (NotRequired[str]) để lưu bản nháp gốc (trước khi rewrite) với title có tiền tố "[DRAFT] ", cho phép user so sánh bản nháp và bản đã sửa.
4. THE ResearchState SHALL tương thích ngược với các node hiện tại không bị ảnh hưởng — các node từ query_gen đến draft không cần thay đổi khi trường scoring bị bỏ.

### Requirement 7: CLI export — 2 file riêng biệt cho bản nháp và bản đã sửa

**User Story:** Là người vận hành pipeline, tôi muốn CLI export cả bản nháp gốc và bản đã sửa thành 2 file markdown riêng biệt, để có thể so sánh trước/sau rewrite.

#### Acceptance Criteria

1. WHEN pipeline hoàn tất, THE CLI SHALL export `draft_post` (bài đã sửa) thành file chính (e.g., `ten-bai-viet.md`).
2. WHEN pipeline hoàn tất và `draft_post_original` tồn tại trong final_state, THE CLI SHALL export `draft_post_original` (bản nháp gốc, title có "[DRAFT]") thành file riêng với suffix `-draft` (e.g., `ten-bai-viet-draft.md`).
3. WHEN export `draft_post_original`, THE CLI SHALL áp dụng cùng post-processing pipeline cho cả 2 file: strip code fence, localize images, prettier formatting.
4. THE CLI SHALL log đường dẫn của cả 2 file đã export trong output summary.
5. WHEN `draft_post_original` không tồn tại trong final_state (e.g., rewrite node không chạy), THE CLI SHALL chỉ export `draft_post` như bình thường và không tạo file `-draft`.
6. THE CLI SHALL lưu `draft_post_original` vào pipeline cache dưới tên `draft-original.md` bên cạnh `draft.md` hiện tại.
7. THE CLI SHALL bỏ hiển thị `Score`, `Revisions` trong summary output (do đã bỏ scoring) và thay bằng đường dẫn cả 2 file.
8. THE CLI SHALL bỏ `review_score`, `review_passed`, `revision_count` khỏi `initial_state` trong lệnh `research`.
