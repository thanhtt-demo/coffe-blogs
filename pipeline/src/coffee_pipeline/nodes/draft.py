import json
import os
import re
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
Bạn là Ba Tê — một người Việt Nam viết blog về cà phê specialty trên blog cá nhân.

## Phong cách viết

- Chuyên sâu, logic, có số liệu và trích dẫn nguồn cụ thể
- Mộc mạc, gần gũi — như đang kể chuyện cho bạn bè nghe
- Dễ hiểu với độc giả phổ thông, kể cả người không làm IT hay học thuật
- Xen kẽ kinh nghiệm cá nhân ("Lần đầu tôi uống...", "Khi rang mẻ đầu tiên...")
- KHÔNG dùng văn mẫu AI sáo rỗng: "Nhìn chung", "Tóm lại", "Có thể nói rằng"
- KHÔNG dùng ẩn dụ, ví dụ hoặc thuật ngữ kiểu kỹ sư/phần mềm/IT như: debug, pipeline, raw/processed, commit message, release note, data replication, dashboard, owner, maintainer
- Nếu có thể diễn đạt bằng từ quen thuộc hằng ngày, luôn ưu tiên cách đó

## Yêu cầu nội dung

**Độ dài:** 800–1400 từ tiếng Việt. Chủ đề đơn giản thì 800–1100 là đủ. \
Ưu tiên mật độ thông tin: mỗi câu phải thêm dữ kiện hoặc góc nhìn mới. \
Cắt mọi câu mang tính đệm, lặp ý, hoặc diễn giải lại điều đã nói.

**Cấu trúc:** 3–5 section chính (##). Mỗi section trả lời đúng 1 câu hỏi \
và KHÔNG lặp luận điểm của section khác. Mỗi section 2–3 đoạn ngắn, \
mỗi đoạn 2–3 câu.

**Mở bài:** 1 anecdote ngắn hoặc câu hỏi kích thích tò mò (tối đa 3–4 câu) — KHÔNG bắt \
đầu bằng "Cà phê là...". Phần thân bài ưu tiên facts và so sánh, hạn chế thêm anecdote.

**Ngôn ngữ:** Ưu tiên câu ngắn, từ quen thuộc, ý rõ ràng. Nếu một ý có thể nói gọn hơn \
thì phải viết gọn hơn. Tránh giải thích dài dòng một điều đã rõ ở câu trước.

**Heading:** Không dùng các heading kiểu mẫu như `## Mở đầu:`, `## Kết luận:`, \
`## Tổng quan:`. Heading phải tự nhiên, đi thẳng vào nội dung, đọc lên giống \
người viết thật chứ không giống dàn bài học sinh.

**Tiêu đề có số đếm:** Chỉ dùng tiêu đề dạng "5 điều", "4 giống", "7 lý do" \
nếu trong bài thực sự có đúng từng ấy ý hoặc từng ấy nhóm được bảo vệ rõ bằng \
nguồn. Nếu không chắc, hãy dùng tiêu đề không có số.

**Định dạng — chỉ dùng khi thật sự giúp bài rõ hơn, KHÔNG cố nhồi đủ loại:**

1. **Hình ảnh** — tối đa 2–4 ảnh. Chèn theo cú pháp:
   ```
   ![Mô tả hình ảnh](URL_ẢNH)
   *Chú thích ngắn*
   ```
   Dùng ĐÚNG URL được cung cấp. TUYỆT ĐỐI KHÔNG tự đặt URL khác.

2. **Bullet points** — chỉ khi có danh sách thực sự (đặc điểm, so sánh). \
   Không bullet chỉ để trang trí.

3. **In đậm / in nghiêng** — tiết chế; chỉ bold số liệu quan trọng, \
   chỉ italic tên khoa học hoặc thuật ngữ nước ngoài.

4. **Trích dẫn** `> ...` — tối đa 1–2 quote trong toàn bài, cho số liệu \
   hoặc nhận định nổi bật nhất.

5. **Bảng Markdown** — chỉ khi so sánh ≥ 3 mục có số liệu cụ thể, \
   không dùng bảng cho nội dung dạng text thuần.

6. **Heading structure:** `##` cho section chính, `###` chỉ khi section dài hơn 4 đoạn.

**Kết bài:** Open-ended, đặt câu hỏi cho độc giả, khuyến khích bình luận. \
Không đặt heading kết bài là "Kết luận" nếu có thể viết một heading tự nhiên hơn.

## Định dạng output

Bắt đầu NGAY bằng YAML frontmatter (---), KHÔNG có text nào trước đó, \
KHÔNG bọc trong code block.
"""


_REF_FILTER_SYSTEM_PROMPT = """\
You are a reference relevance classifier. Given a blog article draft and a list of \
source documents (title + URL), return ONLY a JSON array of indices (0-based) of \
documents that are ACTUALLY RELEVANT to the article content. A document is relevant \
if its subject matter directly supports or is cited in the article. Documents about \
unrelated subjects should be excluded. Return ONLY valid JSON, e.g. [0, 2, 5].\
"""


def _filter_references_llm(draft_text: str, docs: list[dict], topic: str) -> list[dict]:
    """Dùng LLM đánh giá relevance của extracted docs đối với nội dung draft, loại bỏ docs không liên quan.

    Args:
        draft_text: nội dung bài draft từ LLM
        docs: danh sách extracted_docs
        topic: chủ đề bài viết

    Returns:
        Danh sách docs đã lọc (chỉ giữ docs liên quan, không giới hạn số lượng)
    """
    if not docs or not draft_text:
        return []

    if os.getenv("PIPELINE_DRY_RUN"):
        return list(docs)

    # Build user prompt
    docs_lines = []
    for i, doc in enumerate(docs):
        title = doc.get("title", "")
        url = doc.get("url", "")
        docs_lines.append(f"[{i}] Title: {title}\n    URL: {url}")

    user_prompt = (
        f"Topic: {topic}\n\n"
        f"Article draft:\n{draft_text}\n\n"
        f"Source documents:\n" + "\n\n".join(docs_lines)
    )

    try:
        response_text, _usage = call_llm(
            system=_REF_FILTER_SYSTEM_PROMPT,
            user=user_prompt,
            max_tokens=512,
            temperature=0.0,
        )
    except Exception as e:
        print(f"[Draft] LLM ref filter failed, keeping all refs: {e}")
        return list(docs)

    # Parse JSON array of relevant indices
    try:
        indices = json.loads(response_text.strip())
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[Draft] LLM ref filter failed, keeping all refs: {e}")
        return list(docs)

    if not isinstance(indices, list):
        print(f"[Draft] LLM ref filter failed, keeping all refs: unexpected response type")
        return list(docs)

    # Filter docs, skipping out-of-range indices
    filtered = []
    for idx in indices:
        if isinstance(idx, int) and 0 <= idx < len(docs):
            filtered.append(docs[idx])

    kept = len(filtered)
    total = len(docs)
    print(f"[Draft] LLM ref filter: kept {kept}/{total} docs")

    return filtered


def _replace_references_in_draft(draft: str, docs: list[dict], topic: str) -> str:
    """Filter references via LLM and replace the references block in the draft frontmatter.

    If no references block is found in the draft, return the draft as-is.
    """
    # Match the YAML frontmatter (between --- delimiters)
    fm_match = re.match(r"(---\s*\n)(.*?\n)(---)", draft, re.DOTALL)
    if not fm_match:
        return draft

    fm_prefix = fm_match.group(1)   # opening ---\n
    fm_body = fm_match.group(2)     # frontmatter content
    fm_suffix = fm_match.group(3)   # closing ---
    after_fm = draft[fm_match.end():]

    # Find the references block inside frontmatter body
    # Matches "references: []" or "references:\n  - title: ..." block
    refs_pattern = re.compile(
        r"^references:\s*\[\]\s*$|^references:\s*\n(?:  +[^ \n].*\n?)*",
        re.MULTILINE,
    )
    refs_match = refs_pattern.search(fm_body)
    if not refs_match:
        return draft

    # Filter docs via LLM
    filtered_docs = _filter_references_llm(draft, docs, topic)

    # Build new references YAML
    new_refs_yaml = _format_references_yaml(filtered_docs)

    # Replace the old references block with the new one
    new_fm_body = fm_body[:refs_match.start()] + new_refs_yaml + "\n" + fm_body[refs_match.end():]

    return fm_prefix + new_fm_body + fm_suffix + after_fm


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

    # article_images schema: {"cover": {...}|None, "sections": [{...}|None, ...]}
    cover_img = images_data.get("cover") if isinstance(images_data, dict) else None
    section_imgs: list = (
        images_data.get("sections", []) if isinstance(images_data, dict) else []
    )
    cover_url = (
        cover_img["url"] if cover_img
        else CATEGORY_IMAGE_MAP.get(category, CATEGORY_IMAGE_MAP["nghien-cuu"])
    )
    cover_source_id = (
        cover_img.get("source_id") if isinstance(cover_img, dict)
        else _extract_source_id(cover_url)
    )
    today = datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT00:00:00Z")

    # Use title/tags from outline if available
    outline_title = outline.get("title", "")
    outline_excerpt = outline.get("excerpt", "")
    outline_tags = outline.get("tags", [])
    outline_sections = outline.get("sections", [])

    # Build per-section plan: heading + summary + thesis + assigned image (if any)
    sections_lines = []
    for i, sec in enumerate(outline_sections):
        heading = sec.get("heading", "")
        summary = sec.get("summary", "")
        thesis = sec.get("thesis", "")
        img = section_imgs[i] if i < len(section_imgs) else None
        if img:
            line = (
                f"- {heading}: {summary}\n"
                f"  → SAU section này: chèn ảnh ĐÚNG URL này: `{img['url']}`\n"
                f"    Alt text: \"{img['alt']}\"\n"
                f"    Caption: (viết 1 câu tiếng Việt mô tả ngắn)"
            )
        else:
            line = f"- {heading}: {summary}"
        if thesis:
            line += f"\n  → THESIS (chỉ viết quanh luận điểm này): {thesis}"
        sections_lines.append(line)

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
    references_yaml = _format_references_yaml(docs)

    # Frontmatter hints
    tags_yaml = "\n".join(f"  - {t}" for t in (outline_tags or ["cà-phê", "specialty"]))

    user_message = f"""\
Viết bài blog hoàn chỉnh về: **{topic}**

- Category: `{category}`
- PublishDate: `{today}`
- {cover_note}

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
imageSourceId: '{cover_source_id or ''}'
category: {category}
tags:
{tags_yaml}
author: 'Ba Tê'
{references_yaml}
---

Tiếp theo là nội dung bài viết. Chèn ảnh ĐÚNG theo vị trí được chỉ định trong dàn ý, \
dùng cú pháp:
![alt text](URL_ĐÚNG_NHƯ_TRÊN)
*Chú thích tiếng Việt ngắn*

**Quy tắc quan trọng:**
- Mỗi section CHỈ được viết quanh thesis đã gán. Không lạc đề sang luận điểm của section khác.
- Nếu một dữ kiện đã xuất hiện ở section trước, KHÔNG nhắc lại ở section sau.

Nhắc lại lần cuối trước khi viết:
- Viết cho độc giả phổ thông, không giả định họ biết thuật ngữ IT
- Không dùng ví dụ hay ẩn dụ kiểu kỹ sư/phần mềm để giải thích ý
- Nếu hai câu đang nói gần như cùng một ý, giữ lại câu mạnh hơn và bỏ câu còn lại
"""

    # ước tính tokens gửi đi (~4 ky tự/token)
    req_chars = len(_SYSTEM_PROMPT) + len(user_message)
    est_tokens = req_chars // 4
    print(
        f"[Draft] Calling {get_model_label()} | "
        f"~{est_tokens:,} input tokens ({req_chars:,} chars)"
    )

    draft, usage = call_llm(
        system=_SYSTEM_PROMPT,
        user=user_message,
        max_tokens=50000,
        temperature=0.7,
    )
    in_tok = usage.get("inputTokens", "?")
    out_tok = usage.get("outputTokens", "?")
    print(
        f"[Draft] Done | input={in_tok} tok, output={out_tok} tok | "
        f"{len(draft):,} chars"
    )

    # Post-draft: filter references via LLM and rebuild YAML block
    draft = _replace_references_in_draft(draft, docs, topic)

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


def _extract_source_id(url: str | None) -> str:
    if not url:
        return ""

    import re

    match = re.search(r"(photo-[a-z0-9\-]+)", url)
    return match.group(1) if match else url


def _format_references_yaml(docs: list[dict]) -> str:
    references: list[dict] = []
    seen_urls: set[str] = set()

    for doc in docs:
        source_type = doc.get("source_type") or doc.get("source")
        url = doc.get("url")
        title = doc.get("title")

        if not url or not title or source_type == "youtube" or url in seen_urls:
            continue

        references.append(
            {
                "title": title.replace("'", "''"),
                "url": url,
                "source": str(source_type),
            }
        )
        seen_urls.add(url)

        if len(references) >= 6:
            break

    if not references:
        return "references: []"

    lines = ["references:"]
    for reference in references:
        lines.extend(
            [
                f"  - title: '{reference['title']}'",
                f"    url: '{reference['url']}'",
                f"    source: '{reference['source']}'",
            ]
        )

    return "\n".join(lines)


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
        f"imageSourceId: '{_extract_source_id(image_url)}'\n"
        f"category: {category}\n"
        "tags:\n  - dry-run\nauthor: 'Ba Tê'\nreferences: []\n"
        "---\n\n"
        f"# [DRY RUN] {topic}\n\n"
        "Đây là bản draft mock, không gọi Bedrock.\n\n"
        f"Tìm được {num_sources} sources.\n"
    )
