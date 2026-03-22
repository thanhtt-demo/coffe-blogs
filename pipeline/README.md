# Coffee Research Pipeline

AI pipeline tự động nghiên cứu và soạn thảo bài blog cho **Ba Tê và Cà Phê**.

## Kiến trúc

```
[Input: Chủ đề]
      ↓
  query_gen_node       ← LLM sinh 3 query EN + 3 query JA
      ↓
  research_node        ← ArXiv + OpenAlex + DuckDuckGo + YouTube (song song)
      ↓
  extract_node         ← Crawl4AI (web) + YouTube Transcript → cache to disk
      ↓
  outline_node         ← LLM tạo outline + image_query cho từng section
      ↓
  image_fetch_node     ← Unsplash API (1 ảnh cover + 1 ảnh/section)
      ↓
  draft_node           ← LLM viết bài, chèn URL ảnh đã verify
      ↓
  review_node ──────── score >= 8/10 ──→ lưu file .md vào src/data/post/
      ↑                                  + cache outline/images/draft
      └── score < 8/10 (tối đa 3 lần) ──┘
```

## Yêu cầu

| Thành phần | Yêu cầu |
|---|---|
| Python | 3.12+ |
| LLM | OpenAI API key **hoặc** AWS Bedrock access |
| Unsplash | API key miễn phí tại [unsplash.com/developers](https://unsplash.com/developers) |
| Crawl4AI | Playwright Chromium (cài một lần, xem bên dưới) |

## Cài đặt

```bash
cd coffe-blogs/pipeline

# Cài dependencies
pip install -e ".[dev]"

# Lần đầu: cài Playwright Chromium cho Crawl4AI
playwright install chromium
```

## Cấu hình

Tạo file `.env` từ `.env.example`:

```bash
cp .env.example .env
```

Chỉnh sửa `.env`:

```env
# ── LLM Provider ─────────────────────────────────────────────
# Chọn openai (mặc định) hoặc bedrock
LLM_PROVIDER=openai
OPENAI_API_KEY=sk-...
# OPENAI_MODEL_ID=gpt-4o-mini   (mặc định, rẻ hơn)
# OPENAI_MODEL_ID=gpt-4o        (chất lượng cao hơn)

# Hoặc dùng AWS Bedrock:
# LLM_PROVIDER=bedrock
# AWS_PROFILE=default
# AWS_DEFAULT_REGION=us-east-1
# BEDROCK_MODEL_ID=global.anthropic.claude-sonnet-4-6

# ── Unsplash (bắt buộc để có ảnh thực tế, không 404) ─────────
UNSPLASH_ACCESS_KEY=...
```

## Sử dụng

### Viết bài mới

```bash
coffee-research research --topic "lịch sử cà phê Arabica" --category nguon-goc
```

File `.md` được tạo tự động tại `src/data/post/` với frontmatter Astro chuẩn.  
Tất cả artifacts trung gian được cache tại `pipeline/cache/<slug>/`.

### Categories

| Slug | Chủ đề |
|---|---|
| `nguon-goc` | Nguồn gốc, terroir, giống cà phê |
| `rang-xay` | Khoa học rang, hóa học Maillard |
| `pha-che` | Phương pháp pha chế, tỷ lệ, kỹ thuật |
| `nghien-cuu` | Nghiên cứu khoa học, sức khỏe, caffeine |

### Tùy chọn

```
Options:
  --topic TEXT      Chủ đề bài viết (tiếng Việt hoặc Anh)  [required]
  --category TEXT   Category slug  [required]
  --output PATH     Thư mục output (mặc định: ../src/data/post)
  --dry-run         Skip LLM calls, dùng mock response (test local)
```

### Dry-run (test không tốn tiền)

```bash
coffee-research research \
  --topic "pha chế V60" \
  --category pha-che \
  --dry-run
```

## Chạy tests

```bash
cd coffe-blogs/pipeline
pytest tests/ -v
```

## Cấu trúc thư mục

```
pipeline/
├── pyproject.toml
├── .env.example
├── README.md
├── cache/                          # Auto-created, gitignored
│   └── <topic-slug>/
│       ├── sources.json            # Raw search results
│       ├── docs.json               # Extracted content
│       ├── outline.json            # Article outline + image queries
│       ├── images.json             # Verified Unsplash URLs
│       └── draft.md                # Final draft
├── src/
│   └── coffee_pipeline/
│       ├── state.py                # ResearchState TypedDict
│       ├── graph.py                # LangGraph graph definition
│       ├── llm.py                  # LLM abstraction (OpenAI / Bedrock)
│       ├── cli.py                  # CLI entrypoint
│       ├── nodes/
│       │   ├── query_gen.py        # Sinh multilingual search queries
│       │   ├── research.py         # Tìm kiếm song song 4 nguồn
│       │   ├── extract.py          # Crawl & extract + cache to disk
│       │   ├── outline.py          # Tạo outline có per-section image query
│       │   ├── image_fetch.py      # Lấy ảnh thực từ Unsplash
│       │   ├── draft.py            # Viết bài với ảnh đã verify
│       │   └── review.py           # Review và cho điểm
│       └── tools/
│           ├── arxiv_tool.py       # ArXiv academic papers
│           ├── openalex_tool.py    # OpenAlex (100k req/day, no key)
│           ├── web_search_tool.py  # DuckDuckGo web search
│           ├── youtube_tool.py     # YouTube search + view count sort
│           ├── unsplash_tool.py    # Unsplash image fetch
│           └── crawl4ai_tool.py    # Headless browser crawl
└── tests/
    └── test_tools.py
```

## Chi tiết các nodes

### `query_gen_node`
LLM sinh ra 6 search queries (3 tiếng Anh + 3 tiếng Nhật) từ chủ đề gốc — tăng độ phủ nghiên cứu đa ngôn ngữ.

### `research_node`
Tìm kiếm song song từ 4 nguồn (mỗi nguồn chạy với tất cả 6 queries):
- **ArXiv** — academic preprints về coffee science
- **OpenAlex** — 250M+ scholarly papers, miễn phí, 100k request/ngày
- **DuckDuckGo** — web search, ưu tiên domain uy tín (perfectdailygrind.com, ico.org, v.v.)
- **YouTube** — videos sắp xếp theo lượt xem, từ kênh uy tín

### `extract_node`
- ArXiv / OpenAlex → dùng abstract sẵn có (không crawl lại)
- Web URL → **Crawl4AI** Playwright headless (`fit_markdown` — loại bỏ nav/sidebar/ads)
- YouTube → `youtube-transcript-api` (phụ đề, không stream video)

Budget: 15,000 chars/source, tổng 80,000 chars. Kết quả cache vào `pipeline/cache/<slug>/sources.json` và `docs.json`.

### `outline_node`
LLM tạo cấu trúc bài viết: tiêu đề, các section, mô tả nội dung mỗi section, và `image_query` riêng cho từng section.

### `image_fetch_node`
Gọi Unsplash API lấy ảnh thực (không phải URL bịa):
- 1 ảnh cover theo `cover_image_query`
- 1 ảnh per section theo `image_query` của section đó

Trả về `{"cover": {...}, "sections": [{...}, ...]}` — 1:1 với sections.

### `draft_node`
LLM viết bài theo phong cách Ba Tê: chuyên sâu, mộc mạc, không AI-sounding. Mỗi section nhận URL ảnh đã verify để chèn đúng vị trí. Output là file `.md` với YAML frontmatter Astro đầy đủ.

### `review_node`
LLM đánh giá theo 3 tiêu chí (mỗi tiêu chí 0–10):
- **Factual Accuracy** — kiến thức cà phê có đúng không
- **Tone & Style** — tự nhiên, không template, có personality
- **Formatting** — frontmatter và Markdown structure chuẩn

Score trung bình `>= 8.0` → pass. Dưới ngưỡng → feedback chi tiết, quay lại `draft_node`. Tối đa 3 vòng.

## Tech stack

| Package | Version | Dùng để |
|---|---|---|
| `langgraph` | 1.1.3 | Graph orchestration |
| `openai` | ≥1.0.0 | LLM mặc định (gpt-5.4-mini) |
| `boto3` | ≥1.38.0 | AWS Bedrock (tùy chọn) |
| `crawl4ai` | ≥0.5.0 | Headless browser crawl |
| `arxiv` | ≥2.1.3 | ArXiv API |
| `httpx` | ≥0.28.0 | OpenAlex API |
| `duckduckgo-search` | ≥7.0.0 | Web search (no API key) |
| `yt-dlp` | ≥2025.1.1 | YouTube search |
| `youtube-transcript-api` | ≥0.6.3 | YouTube transcript |
| `python-slugify` | ≥8.0.4 | Tạo filename từ tiêu đề |
| `click` | ≥8.1.8 | CLI |
