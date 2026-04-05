"""Rewrite node — sửa bài viết dựa trên review feedback.

Targeted replacements, không viết lại toàn bộ. Lưu bản gốc vào
``draft_post_original`` với title có tiền tố "[DRAFT] ".
"""

import json
import logging
import os
import re

from ..llm import call_llm, get_model_label
from ..state import ResearchState

logger = logging.getLogger(__name__)

_REWRITE_SYSTEM = """\
Bạn là biên tập viên chuyên nghiệp về nội dung cà phê và khoa học thực phẩm.

Nhiệm vụ: nhận bài viết gốc và danh sách các vấn đề cần sửa, thực hiện \
targeted replacements cho từng vấn đề. KHÔNG viết lại toàn bộ bài viết.

Quy tắc:
1. Giữ nguyên TOÀN BỘ YAML frontmatter (bao gồm title gốc — KHÔNG thêm "[DRAFT] " \
hay bất kỳ tiền tố nào vào title).
2. Giữ nguyên tất cả headings (##, ###) và thứ tự các section.
3. Giữ nguyên tất cả hình ảnh: URL, alt text, và vị trí chèn hình ảnh.
4. Chỉ sửa các đoạn văn được chỉ ra trong danh sách vấn đề.
5. Áp dụng gợi ý sửa (suggestion) cho từng vấn đề.
6. Giữ nguyên phần còn lại của bài viết.

Output: bài viết hoàn chỉnh đã sửa (bao gồm YAML frontmatter). \
KHÔNG thêm giải thích hay ghi chú nào khác.
"""


def _add_draft_prefix_to_title(content: str) -> str:
    """Thêm tiền tố ``[DRAFT] `` vào giá trị ``title`` trong YAML frontmatter."""

    # Match frontmatter block (between --- delimiters)
    fm_match = re.match(r"(---\s*\n)(.*?\n)(---)", content, re.DOTALL)
    if not fm_match:
        return content

    before = fm_match.group(1)
    fm_body = fm_match.group(2)
    after_delim = fm_match.group(3)
    rest = content[fm_match.end():]

    def _replace_title(m: re.Match) -> str:
        prefix = m.group(1)  # "title: " (or "title:  ")
        quote = m.group(2)   # opening quote character (' or ") — or None
        quoted_val = m.group(3)    # title text inside quotes — or None
        unquoted_val = m.group(4)  # unquoted title text — or None

        if quote and quoted_val is not None:
            # Quoted title: title: 'X' → title: '[DRAFT] X'
            return f"{prefix}{quote}[DRAFT] {quoted_val}{quote}"
        else:
            # Unquoted title: title: X → title: '[DRAFT] X'
            val = (unquoted_val or "").rstrip()
            return f"{prefix}'[DRAFT] {val}'"

    new_fm_body = re.sub(
        r"""^(title:\s*)(?:(['"])(.*?)\2|(.*))$""",
        _replace_title,
        fm_body,
        count=1,
        flags=re.MULTILINE,
    )

    return f"{before}{new_fm_body}{after_delim}{rest}"


def rewrite_node(state: ResearchState) -> dict:
    """Sửa bài viết dựa trên review feedback. Targeted replacements, không viết lại toàn bộ."""

    draft = state["draft_post"]
    feedback_raw = state.get("review_feedback", "") or ""

    print(f"[Rewrite] review_feedback from state: {len(feedback_raw)} chars, empty={not feedback_raw.strip()}")

    # 1. Tạo draft_post_original (bản gốc với title "[DRAFT] ")
    draft_post_original = _add_draft_prefix_to_title(draft)

    # Dry-run mode: skip LLM
    if os.getenv("PIPELINE_DRY_RUN"):
        print("[Rewrite] DRY RUN -- skipping LLM")
        return {"draft_post": draft, "draft_post_original": draft_post_original}

    # 2. Empty feedback → return unchanged
    if not feedback_raw.strip():
        print("[Rewrite] Empty feedback — skipping LLM")
        return {"draft_post": draft, "draft_post_original": draft_post_original}

    # 3. Parse review feedback
    json_parsed = False
    issues: list[dict] = []
    feedback_text = feedback_raw  # fallback: raw text for LLM

    try:
        parsed = json.loads(feedback_raw)
        issues = parsed.get("issues", [])
        json_parsed = True
    except (json.JSONDecodeError, TypeError):
        # JSON parse failed — use raw text as feedback (best effort)
        logger.warning("[Rewrite] JSON parse failed, using raw text as feedback")
        print("[Rewrite] JSON parse failed, using raw text as feedback")

    # 4. Parsed JSON with no issues → return unchanged, skip LLM
    if json_parsed and not issues:
        print("[Rewrite] No issues found — skipping LLM")
        return {"draft_post": draft, "draft_post_original": draft_post_original}

    # 5. Gọi LLM để sửa bài
    user_message = (
        "BÀI VIẾT GỐC:\n\n"
        f"{draft}\n\n"
        "---\n"
        "DANH SÁCH VẤN ĐỀ CẦN SỬA:\n\n"
        f"{feedback_text}"
    )

    req_chars = len(_REWRITE_SYSTEM) + len(user_message)
    est_tokens = req_chars // 4
    print(
        f"[Rewrite] Calling {get_model_label()} | "
        f"~{est_tokens:,} input tokens ({req_chars:,} chars)"
    )

    try:
        rewritten, usage = call_llm(
            system=_REWRITE_SYSTEM,
            user=user_message,
            max_tokens=16384,
            temperature=0.3,
        )
    except Exception as exc:
        logger.warning("[Rewrite] LLM call failed: %s", exc)
        print(f"[Rewrite] LLM call failed: {exc}")
        return {"draft_post": draft, "draft_post_original": draft_post_original}

    in_tok = usage.get("inputTokens", "?")
    out_tok = usage.get("outputTokens", "?")
    print(f"[Rewrite] Response: input={in_tok} tok, output={out_tok} tok")

    corrected = rewritten.strip()
    return {"draft_post": corrected, "draft_post_original": draft_post_original}
