"""Review node — đánh giá toàn diện bài viết (nội dung + ngôn ngữ tiếng Việt).

Output là danh sách vấn đề cụ thể dạng JSON có cấu trúc, không scoring.
"""

import json
import logging
import os
import re

from ..llm import call_llm, get_model_label
from ..state import ResearchState

logger = logging.getLogger(__name__)

_REVIEW_SYSTEM = """\
Bạn là biên tập viên chuyên nghiệp về nội dung cà phê và khoa học thực phẩm.

Nhiệm vụ: đọc bài blog và liệt kê TẤT CẢ các vấn đề cần sửa. Đánh giá theo 7 khía cạnh:

1. **Factual accuracy** — dữ kiện cà phê sai, số liệu không chính xác, tên giống/quy trình sai.
2. **Tone & style** — câu sáo rỗng kiểu AI, thiếu personality, dùng ẩn dụ/thuật ngữ IT \
(debug, pipeline, raw/processed, commit, release, replication, dashboard, owner).
3. **Concision** — đoạn lặp ý, câu đệm không thêm thông tin mới, giải thích rườm rà.
4. **Formatting** — lỗi YAML frontmatter, markdown structure không hợp lý.
5. **Cross-section repetition** — luận điểm hoặc dữ kiện xuất hiện ở nhiều section.
6. **Reference alignment** — reference không liên quan đến nội dung, hoặc nguồn được nhắc \
đến nhưng thiếu trong references.
7. **Vietnamese naturalness** — cụm từ thụ động không tự nhiên, từ dịch sát tiếng Anh, \
thuật ngữ chuyên ngành dịch thô chưa Việt hóa, từ ngữ lạc ngữ cảnh cà phê, \
câu cứng thiếu tính miêu tả cảm giác.

KHÔNG cho điểm. KHÔNG đánh giá pass/fail. Chỉ liệt kê vấn đề cụ thể.

Trả về JSON duy nhất (KHÔNG có text nào khác):
{
  "issues": [
    {
      "original": "trích nguyên văn đoạn có vấn đề",
      "category": "naturalness | factual | tone | concision | formatting | repetition | references",
      "suggestion": "gợi ý sửa cụ thể"
    }
  ]
}

Nếu không tìm thấy vấn đề nào, trả về: {"issues": []}
"""


def review_node(state: ResearchState) -> dict:
    """Đánh giá toàn diện bài viết, trả về danh sách vấn đề cần sửa."""

    # Dry-run mode: skip LLM
    if os.getenv("PIPELINE_DRY_RUN"):
        print("[Review] DRY RUN -- skipping LLM")
        return {"review_feedback": ""}

    draft = state["draft_post"]
    topic = state["topic"]

    user_message = (
        f'Review bài viết blog về "{topic}".\n\n'
        f"---\nBÀI VIẾT CẦN REVIEW:\n\n{draft}"
    )

    req_chars = len(_REVIEW_SYSTEM) + len(user_message)
    est_tokens = req_chars // 4
    print(
        f"[Review] Calling {get_model_label()} | "
        f"~{est_tokens:,} input tokens ({req_chars:,} chars)"
    )

    try:
        raw_text, usage = call_llm(
            system=_REVIEW_SYSTEM,
            user=user_message,
            max_tokens=4096,
            temperature=0.2,
        )
    except Exception as exc:
        logger.warning("[Review] LLM call failed: %s", exc)
        print(f"[Review] LLM call failed: {exc}")
        return {"review_feedback": ""}

    in_tok = usage.get("inputTokens", "?")
    out_tok = usage.get("outputTokens", "?")
    print(f"[Review] Response: input={in_tok} tok, output={out_tok} tok")

    raw = raw_text.strip()

    # Try to extract JSON from response (LLM may wrap in code block)
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group())
            feedback_str = json.dumps(result, ensure_ascii=False)
            n_issues = len(result.get("issues", []))
            print(f"[Review] Found {n_issues} issue(s)")
            return {"review_feedback": feedback_str}
        except json.JSONDecodeError:
            print(f"[Review] JSON decode failed on: {json_match.group()[:200]}...")

    # Fallback: JSON parse failed — save raw text
    logger.warning("[Review] JSON parse failed, using raw text")
    print(f"[Review] JSON parse failed, using raw text as feedback ({len(raw)} chars)")
    return {"review_feedback": raw}
