import json
import re

from ..llm import call_llm
from ..state import ResearchState

_SYSTEM_PROMPT = """\
You are an expert Vietnamese coffee blog editor. Given research materials about a \
coffee topic, create a detailed article outline in Vietnamese.

Output ONLY valid JSON (no markdown, no explanation, no code fence):
{
  "title": "Tiêu đề kích thích sự tò mò — xem quy tắc bên dưới",
  "excerpt": "Hook ngắn, max 200 ký tự",
  "cover_image_query": "english query for the hero/cover image of the whole article",
  "sections": [
    {
      "heading": "## Tên section",
      "summary": "Nội dung chính sẽ viết, 2-3 câu",
      "thesis": "Luận điểm chính duy nhất của section này, tối đa 1 câu",
      "image_query": "specific english visual query matching THIS section's content"
    }
  ],
  "tags": ["slug-tag-1", "slug-tag-2", "slug-tag-3"]
}

Rules:
- 5–8 sections (including intro and conclusion)
- title: MUST be curiosity-triggering and interesting. Use one of these techniques:
    * Surprising fact: "Vì Sao Cà Phê Việt Nam Đắng Hơn Bất Kỳ Nơi Nào Trên Thế Giới?"
    * Contrast/paradox: "Hạt Cà Phê Rẻ Nhất Thế Giới Lại Là Nguyên Liệu Của Ly Espresso Đắt Nhất"
    * Number + promise: "5 Điều Về Cà Phê Arabica Mà Ngay Cả Barista Cũng Không Biết"
    * Secret/hidden: "Bí Mật Đằng Sau Vị Chua Nhẹ Trong Cà Phê Đà Lạt"
    * Challenge assumption: "Bạn Uống Cà Phê Sai Cách Suốt Bao Nhiêu Năm Qua?"
  Title must be in Vietnamese, max 80 characters, no generic phrases like "Khám phá" or "Tìm hiểu".
    If title contains a number, that number MUST exactly match the real count defended by the article and sources.
    Do NOT count overlapping parent-child groups as separate items unless the taxonomy is explicitly justified.
- cover_image_query: broad visual query for the article as a whole
- image_query per section: MUST match the specific subject of THAT section.
  Examples: if section is about Robusta → "robusta coffee plant closeup vietnam";
  if section is about Yemen trade history → "historic mocha port yemen coffee";
  if section is about flavor profiles → "specialty coffee cupping tasting notes".
  NOT generic like "coffee beans" — be precise.
- Not every section needs an image. Set image_query to null for intro/conclusion.
- Section headings must sound natural. Do NOT use headings like "## Mở đầu:", "## Kết luận:", "## Tổng quan:".
- Use direct, content-specific headings instead, for example a question or a statement that can stand on its own.
- tags: lowercase, hyphenated, 3–5 tags
- All Vietnamese text must be natural, not translated-sounding
- Mỗi section PHẢI có một `thesis` riêng biệt — luận điểm chính duy nhất mà section đó bảo vệ, viết trong tối đa 1 câu.
- KHÔNG section nào được lặp lại luận điểm của section khác. Nếu hai section có thesis giống nhau, hãy gộp chúng lại.
"""


def _parse_outline(raw: str) -> dict:
    text = raw.strip()
    # Strip code fences
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    text = text.strip()
    # Try full parse first
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Try to extract the outermost JSON object (handles preamble text or truncated output)
    start = text.find("{")
    if start != -1:
        # Walk backwards from end to find last valid closing brace
        for end in range(len(text), start, -1):
            try:
                return json.loads(text[start:end])
            except json.JSONDecodeError:
                continue
    return {}


def outline_node(state: ResearchState) -> dict:
    """Node 3a: Dùng LLM tạo dàn ý + danh sách image queries trước khi viết bài."""
    topic = state["topic"]
    docs = state.get("extracted_docs", [])

    # Include all docs — use full content (truncated per doc to fit context)
    max_per_doc = max(500, 200000 // max(len(docs), 1))
    docs_brief = "\n".join(
        f"- [{d['source_type']}] {d['title']}:\n{d['content'][:max_per_doc]}"
        for d in docs
    )

    print(f"[Outline] Generating outline for: {topic!r} ({len(docs)} docs)")

    text, usage = call_llm(
        system=_SYSTEM_PROMPT,
        user=f"Topic: {topic}\n\nResearch materials:\n{docs_brief}",
        max_tokens=2048,
        temperature=0.4,
    )
    print(
        f"[Outline] {usage.get('outputTokens', '?')} output tokens | "
        f"raw: {text[:120]!r}..."
    )

    outline = _parse_outline(text)
    if not outline:
        print("[Outline] WARNING: failed to parse outline JSON, using empty outline")
        outline = {
            "title": topic,
            "excerpt": "",
            "cover_image_query": f"specialty coffee {topic}",
            "sections": [],
            "tags": [],
        }
    else:
        n_sections = len(outline.get("sections", []))
        img_sections = sum(
            1 for s in outline.get("sections", []) if s.get("image_query")
        )
        print(f"[Outline] {n_sections} sections, {img_sections} with image queries")
        print(f"[Outline] Cover query: {outline.get('cover_image_query', '')}")
        for s in outline.get("sections", []):
            if s.get("image_query"):
                print(f"[Outline]   {s['heading'][:40]} → {s['image_query']!r}")

    return {"article_outline": outline}
