# Requirements Document

## Giới thiệu

Pipeline tạo bài blog tự động cho "Ba Tê và Cà Phê" hiện có 3 vấn đề chất lượng nội dung:
1. Nội dung lặp lại giữa các section trong cùng một bài viết
2. Danh sách references không khớp với nội dung thực tế của bài draft
3. Review node quá dễ dãi, không phát hiện được lặp nội dung và sai lệch references

Feature này cải thiện chất lượng output của pipeline bằng cách thêm ràng buộc uniqueness vào outline, lọc references theo nội dung thực tế, và nâng cấp review node với kiểm tra có cấu trúc.

## Glossary

- **Pipeline**: Hệ thống LangGraph tự động tạo bài blog, gồm các node: query_gen → research → extract → outline → image_fetch → draft → review
- **Outline_Node**: Node tạo dàn ý bài viết (file `outline.py`), output là JSON chứa title, excerpt, sections, tags
- **Draft_Node**: Node viết bài hoàn chỉnh từ dàn ý và tài liệu nghiên cứu (file `draft.py`)
- **Review_Node**: Node đánh giá chất lượng bài viết, cho điểm và feedback (file `review.py`)
- **Research_Node**: Node tìm kiếm tài liệu từ ArXiv, OpenAlex, Web, YouTube (file `research.py`)
- **Extract_Node**: Node trích xuất nội dung từ các nguồn tìm được (file `extract.py`)
- **Section**: Một phần nội dung trong bài viết, tương ứng với một heading `##`
- **Thesis**: Luận điểm chính duy nhất mà một section bảo vệ
- **References**: Danh sách nguồn tham khảo trong YAML frontmatter của bài viết
- **Extracted_Docs**: Danh sách tài liệu đã trích xuất nội dung, lưu trong state
- **ResearchState**: TypedDict định nghĩa state của pipeline (file `state.py`)
- **Relevance_Score**: Điểm đánh giá mức độ liên quan giữa một tài liệu và chủ đề bài viết

## Requirements

### Requirement 1: Outline Node — Ràng buộc uniqueness giữa các section

**User Story:** Là người vận hành pipeline, tôi muốn mỗi section trong dàn ý có một thesis riêng biệt không trùng lặp với section khác, để bài viết không bị lặp ý giữa các phần.

#### Acceptance Criteria

1. WHEN Outline_Node tạo dàn ý, THE Outline_Node SHALL yêu cầu LLM sinh thêm trường `thesis` cho mỗi section, mô tả luận điểm chính duy nhất của section đó trong tối đa 1 câu.
2. WHEN Outline_Node tạo dàn ý, THE Outline_Node SHALL bao gồm trong system prompt quy tắc rằng mỗi section phải có thesis khác biệt và không section nào được lặp lại luận điểm của section khác.
3. WHEN Draft_Node nhận dàn ý có trường `thesis`, THE Draft_Node SHALL đưa thesis của từng section vào prompt để LLM biết mỗi section chỉ được viết quanh luận điểm đã gán.
4. WHEN Draft_Node xây dựng prompt, THE Draft_Node SHALL bao gồm chỉ dẫn rõ ràng rằng nếu một dữ kiện đã xuất hiện ở section trước thì không được nhắc lại ở section sau.

### Requirement 2: Lọc references theo nội dung thực tế của bài draft

**User Story:** Là người vận hành pipeline, tôi muốn danh sách references trong frontmatter chỉ chứa những nguồn thực sự được trích dẫn hoặc liên quan trực tiếp đến nội dung bài viết, để độc giả không thấy references vô nghĩa như bài vật lý hay thiên văn trong bài về sức khỏe cà phê.

#### Acceptance Criteria

1. WHEN Draft_Node tạo references YAML, THE Draft_Node SHALL gọi LLM một lần duy nhất để đánh giá từng extracted doc có liên quan đến nội dung bài draft hay không, dựa trên title, URL và chủ đề của doc so với nội dung draft.
2. WHEN LLM đánh giá một extracted doc không liên quan đến nội dung bài draft, THE Draft_Node SHALL loại doc đó khỏi danh sách references.
3. WHEN Draft_Node hoàn tất lọc references, THE Draft_Node SHALL giữ lại tất cả references đã qua lọc mà LLM đánh giá là liên quan, không giới hạn số lượng cứng.
4. THE Draft_Node SHALL thực hiện bước lọc references SAU khi LLM trả về bài draft, không phải trước khi gọi LLM.
5. WHEN LLM call bị lỗi (network, parse error), THE Draft_Node SHALL giữ lại tất cả references (fallback an toàn) và ghi log warning.

### Requirement 3: Lọc relevance tại Extract Node

**User Story:** Là người vận hành pipeline, tôi muốn Extract_Node loại bỏ các tài liệu không liên quan đến chủ đề bài viết ngay từ giai đoạn trích xuất, để các node phía sau không phải xử lý dữ liệu nhiễu.

#### Acceptance Criteria

1. WHEN Extract_Node xử lý tài liệu từ nguồn academic (arxiv, semantic_scholar, openalex), THE Extract_Node SHALL gom tất cả tài liệu academic vào một batch và gọi LLM một lần duy nhất để đánh giá relevance của từng tài liệu đối với chủ đề cà phê và topic cụ thể của bài viết.
2. WHEN LLM đánh giá một tài liệu academic là không liên quan đến chủ đề cà phê hoặc topic bài viết, THE Extract_Node SHALL loại bỏ tài liệu đó và ghi log lý do loại bỏ.
3. WHEN Extract_Node hoàn tất lọc, THE Extract_Node SHALL ghi log số lượng tài liệu được giữ lại so với tổng số tài liệu đầu vào.
4. WHEN LLM call bị lỗi (network, parse error), THE Extract_Node SHALL giữ lại tất cả tài liệu academic (fallback an toàn) và ghi log warning.

### Requirement 4: Review Node — Kiểm tra lặp nội dung có cấu trúc

**User Story:** Là người vận hành pipeline, tôi muốn Review_Node phát hiện được các trường hợp lặp luận điểm giữa các section, để bài viết bị lặp ý sẽ bị trừ điểm và yêu cầu sửa cụ thể.

#### Acceptance Criteria

1. WHEN Review_Node đánh giá bài viết, THE Review_Node SHALL thêm tiêu chí đánh giá thứ 5 là "Cross-Section Repetition" (0-10), kiểm tra xem có luận điểm, dữ kiện, hoặc câu diễn đạt gần giống nhau xuất hiện ở nhiều section hay không.
2. WHEN Review_Node phát hiện một luận điểm hoặc dữ kiện xuất hiện ở 2 section trở lên, THE Review_Node SHALL liệt kê cụ thể luận điểm bị lặp và các section chứa nó trong phần feedback.
3. WHEN Review_Node tính điểm tổng, THE Review_Node SHALL tính trung bình của 5 tiêu chí (bao gồm Cross-Section Repetition) thay vì 4 tiêu chí như hiện tại.

### Requirement 5: Review Node — Kiểm tra references-content alignment

**User Story:** Là người vận hành pipeline, tôi muốn Review_Node kiểm tra xem danh sách references trong frontmatter có khớp với nội dung thực tế của bài viết hay không, để phát hiện references không liên quan hoặc nguồn được trích dẫn nhưng thiếu trong references.

#### Acceptance Criteria

1. WHEN Review_Node đánh giá bài viết, THE Review_Node SHALL thêm tiêu chí đánh giá thứ 6 là "Reference Alignment" (0-10), kiểm tra mức độ khớp giữa danh sách references trong frontmatter và nội dung thực tế của bài viết.
2. WHEN một reference trong frontmatter không có liên quan rõ ràng đến bất kỳ nội dung nào trong bài viết, THE Review_Node SHALL ghi nhận reference đó là "không liên quan" trong feedback.
3. WHEN bài viết nhắc đến một nguồn cụ thể (tên tổ chức, tên nghiên cứu, URL) mà nguồn đó không có trong danh sách references, THE Review_Node SHALL ghi nhận nguồn đó là "thiếu trong references" trong feedback.
4. WHEN Review_Node tính điểm tổng, THE Review_Node SHALL tính trung bình của 6 tiêu chí thay vì 4 tiêu chí như hiện tại.

### Requirement 6: Cập nhật ResearchState cho các trường mới

**User Story:** Là developer bảo trì pipeline, tôi muốn ResearchState được cập nhật để phản ánh các trường dữ liệu mới phát sinh từ việc cải thiện chất lượng, để type checking hoạt động chính xác.

#### Acceptance Criteria

1. WHEN outline chứa trường `thesis` cho mỗi section, THE ResearchState SHALL vẫn tương thích vì `article_outline` đã là kiểu `dict` và không cần thay đổi schema.
2. WHEN Review_Node trả về kết quả với 6 tiêu chí, THE ResearchState SHALL vẫn tương thích vì `review_feedback` đã là kiểu `str` và `review_score` đã là kiểu `float`.
