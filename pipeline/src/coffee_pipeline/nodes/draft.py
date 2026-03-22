import json
import os
from datetime import datetime, timezone

from ..llm import call_llm, get_model_label
from ..state import ResearchState

# Map category → Unsplash image đã được dùng trong các bài mẫu
CATEGORY_IMAGE_MAP = {
    "nguon-goc": (
        "https://images.unsplash.com/photo-1501339847302-ac426a4a7cbb"
        "?ixlib=rb-4.0.3&auto=format&fit=crop&w=1740&q=80"
    ),
    "rang-xay": (
        "https://images.unsplash.com/photo-1559496417-e7f25cb247f3"
        "?ixlib=rb-4.0.3&auto=format&fit=crop&w=1920&q=80"
    ),
    "pha-che": (
        "https://images.unsplash.com/photo-1495474472287-4d71bcdd2085"
        "?ixlib=rb-4.0.3&auto=format&fit=crop&w=1740&q=80"
    ),
    "nghien-cuu": (
        "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d"
        "?ixlib=rb-4.0.3&auto=format&fit=crop&w=1740&q=80"
    ),
}

_SYSTEM_PROMPT = """\
Bạn là Ba Tê — một Data Engineer người Việt Nam đang chia sẻ niềm đam mê cà phê \
specialty trên blog cá nhân.

## Phong cách viết

- Chuyên sâu, logic, có số liệu và trích dẫn nguồn cụ thể
- Mộc mạc, gần gũi — như đang kể chuyện cho bạn bè nghe
- Xen kẽ kinh nghiệm cá nhân ("Lần đầu tôi uống...", "Khi rang mẻ đầu tiên...")
- KHÔNG dùng văn mẫu AI sáo rỗng: "Nhìn chung", "Tóm lại", "Có thể nói rằng"

## Yêu cầu nội dung

**Độ dài:** 1500–4500 từ tiếng Việt (tùy vào độ khó mà có thể linh hoạt, nhưng ưu tiên sâu hơn thay vì dài thêm).

**Mở bài:** Bắt đầu bằng anecdote hoặc câu hỏi kích thích tò mò — KHÔNG bắt \
đầu bằng "Cà phê là..."

**Định dạng phong phú — bắt buộc dùng đủ các yếu tố sau:**

1. **Hình ảnh minh hậa xen kẽ** — chèn ảnh vào giữa bài theo cú pháp:
   ```
   ![Mô tả hình ảnh](URL_ẢNH)
   *Chú thích ngắn, bổ sung ngữ cảnh*
   ```
   Dùng ĐÚNG URL được cung cấp trong phần "Hình ảnh có sẵn". TUYỆT ĐỐI KHÔNG tự đặt URL khác.

2. **Bullet points có tổ chức** — dùng cho danh sách đặc điểm, so sánh, \
   quy trình. Mỗi bullet nên có 1–2 câu, không phải chỉ một từ.

3. **In đậm** `**...**` — dùng để nhấn mạnh số liệu quan trọng, tên kỹ thuật, \
   thuật ngữ cà phê lần đầu xuất hiện.

4. **In nghiêng** `*...*` — dùng cho tên khoa học (*Coffea arabica*), tên nước \
   ngoài, và những cảm nhận chủ quan ("*hương thơm như caramel và hoa nhài*").

5. **Trích dẫn** `> ...` — dùng cho câu nói của chuyên gia, số liệu từ nghiên \
   cứu, hoặc câu tóm tắt ý quan trọng nhất của đoạn. Ví dụ:
   > "Arabica chiếm 60% sản lượng cà phê toàn cầu và được trồng ở độ cao \
   > 600–2.000m so với mực nước biển." — ICO, 2023

6. **Bảng Markdown** — khi cần so sánh số liệu hoặc đặc điểm giữa 2+ đối tượng.

7. **Heading structure:** `##` cho section chính, `###` cho sub-section.

**Kết bài:** Open-ended, đặt câu hỏi cho độc giả, khuyến khích bình luận.

## Định dạng output

Bắt đầu NGAY bằng YAML frontmatter (---), KHÔNG có text nào trước đó, \
KHÔNG bọc trong code block.
"""


def draft_node(state: ResearchState) -> dict:
    """Node 5: Tổng hợp tài liệu và viết bản nháp bài blog."""
    # Dry-run mode: skip LLM call
    if os.getenv("PIPELINE_DRY_RUN"):
        return {"draft_post": _mock_draft(state)}

    topic = state["topic"]
    category = state["category"]
    docs = state["extracted_docs"]
    outline: dict = state.get("article_outline") or {}  # type: ignore[assignment]
    images_data: dict = state.get("article_images") or {}  # type: ignore[assignment]
    feedback = state.get("review_feedback", "")
    revision_count = state.get("revision_count", 0)

    # article_images schema: {"cover": {...}|None, "sections": [{...}|None, ...]}
    cover_img = images_data.get("cover") if isinstance(images_data, dict) else None
    section_imgs: list = (
        images_data.get("sections", []) if isinstance(images_data, dict) else []
    )
    cover_url = (
        cover_img["url"] if cover_img
        else CATEGORY_IMAGE_MAP.get(category, CATEGORY_IMAGE_MAP["nghien-cuu"])
    )
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

    # Use title/tags from outline if available
    outline_title = outline.get("title", "")
    outline_excerpt = outline.get("excerpt", "")
    outline_tags = outline.get("tags", [])
    outline_sections = outline.get("sections", [])

    revision_note = ""
    if feedback and revision_count > 0:
        revision_note = (
            f"\n\n**⚠️ Feedback từ review lần {revision_count} (bắt buộc sửa):**\n"
            f"{feedback}\n"
        )

    # Build per-section plan: heading + summary + assigned image (if any)
    sections_lines = []
    for i, sec in enumerate(outline_sections):
        heading = sec.get("heading", "")
        summary = sec.get("summary", "")
        img = section_imgs[i] if i < len(section_imgs) else None
        if img:
            sections_lines.append(
                f"- {heading}: {summary}\n"
                f"  → SAU section này: chèn ảnh ĐÚNG URL này: `{img['url']}`\n"
                f"    Alt text: \"{img['alt']}\"\n"
                f"    Caption: (viết 1 câu tiếng Việt mô tả ngắn)"
            )
        else:
            sections_lines.append(f"- {heading}: {summary}")

    sections_block = (
        "**Dàn ý + vị trí ảnh (theo thứ tự, KHÔNG thay đổi URL):**\n"
        + "\n".join(sections_lines)
        if sections_lines else ""
    )

    cover_note = (
        f"Cover image (dùng ĐÚNG URL này trong frontmatter): `{cover_url}`"
        + (f"\n  (photographer: {cover_img['photographer']})" if cover_img else "")
    )

    sources_block = _format_sources(docs)

    # Frontmatter hints
    tags_yaml = "\n".join(f"  - {t}" for t in (outline_tags or ["cà-phê", "specialty"]))

    user_message = f"""\
Viết bài blog hoàn chỉnh về: **{topic}**

- Category: `{category}`
- PublishDate: `{today}`
- {cover_note}
{revision_note}
---

{sections_block}

---

**Nguồn tài liệu:**

{sources_block}

---

**Output format — bắt đầu ngay bằng frontmatter, không có text trước đó:**

---
publishDate: {today}
title: '{outline_title or topic}'
excerpt: '{outline_excerpt or ""}'
image: '{cover_url}'
category: {category}
tags:
{tags_yaml}
author: 'Ba Tê'
---

Tiếp theo là nội dung bài viết. Chèn ảnh ĐÚNG theo vị trí được chỉ định trong dàn ý, \
dùng cú pháp:
![alt text](URL_ĐÚNG_NHƯ_TRÊN)
*Chú thích tiếng Việt ngắn*
"""

    # ước tính tokens gửi đi (~4 ky tự/token)
    req_chars = len(_SYSTEM_PROMPT) + len(user_message)
    est_tokens = req_chars // 4
    print(
        f"[Draft] Calling {get_model_label()} | "
        f"~{est_tokens:,} input tokens ({req_chars:,} chars) | "
        f"revision #{revision_count + 1}"
    )

    draft, usage = call_llm(
        system=_SYSTEM_PROMPT,
        user=user_message,
        max_tokens=50000,
        temperature=0.7,
    )
    in_tok  = usage.get("inputTokens",  "?")
    out_tok = usage.get("outputTokens", "?")
    print(
        f"[Draft] Done | input={in_tok} tok, output={out_tok} tok | "
        f"{len(draft):,} chars"
    )
    return {"draft_post": draft}


def _format_sources(docs: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        parts.append(
            f"### Nguồn {i}: {doc['title']}\n"
            f"- URL: {doc['url']}\n"
            f"- Type: {doc['source_type']}\n\n"
            f"{doc['content']}"
        )
    return "\n\n---\n\n".join(parts)


def _mock_draft(state: ResearchState) -> str:
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT00:00:00Z")
    category = state["category"]
    image_url = CATEGORY_IMAGE_MAP.get(category, CATEGORY_IMAGE_MAP["nghien-cuu"])
    topic = state["topic"]
    num_sources = len(state.get("extracted_docs", []))
    return (
        "---\n"
        f"publishDate: {today}\n"
        f"title: '[DRY RUN] {topic}'\n"
        "excerpt: 'Bài viết dry-run để test pipeline'\n"
        f"image: '{image_url}'\n"
        f"category: {category}\n"
        "tags:\n  - dry-run\nauthor: 'Ba Tê'\n"
        "---\n\n"
        f"# [DRY RUN] {topic}\n\n"
        "Đây là bản draft mock, không gọi Bedrock.\n\n"
        f"Tìm được {num_sources} sources.\n"
    )
