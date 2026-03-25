import json
import os
import re

from ..llm import call_llm, get_model_label
from ..state import ResearchState
_PASS_THRESHOLD = 8.0

_REVIEW_SYSTEM = """\
Bạn là biên tập viên chuyên nghiệp về nội dung cà phê và khoa học thực phẩm.
Nhiệm vụ: review bài blog và trả về JSON đánh giá.
Chỉ trả về JSON, không có text nào khác.
"""


def review_node(state: ResearchState) -> dict:
    """Node 4: Review bản nháp, cho điểm và feedback. Increment revision_count."""
    revision_count = state.get("revision_count", 0)

    # Dry-run mode: auto-pass
    if os.getenv("PIPELINE_DRY_RUN"):
        print("[Review] DRY RUN -- auto-pass")
        return {
            "review_score": 9.0,
            "review_passed": True,
            "review_feedback": "Approved (dry-run)",
            "revision_count": revision_count + 1,
        }

    draft = state["draft_post"]
    topic = state["topic"]

    user_message = f"""\
Review bài viết blog về "{topic}" theo 4 tiêu chí sau:

1. **Factual Accuracy** (0-10): Kiến thức cà phê có đúng không? \
Có lỗi khoa học nào (nhiệt độ, phản ứng hóa học, tên giống cà phê)? Nếu title có số đếm \
thì kiểm tra số đó có đúng với nội dung và taxonomy được bài bảo vệ hay không.
2. **Tone & Style** (0-10): Ngôn từ có tự nhiên không? Có bị AI-sounding \
(sáo rỗng, quá template, không có personality)? Có giống một người yêu \
cà phê đang chia sẻ thật với độc giả phổ thông không? Trừ điểm rõ rệt nếu dùng \
ẩn dụ hoặc ví dụ kiểu kỹ sư/phần mềm/IT như debug, pipeline, raw/processed, \
commit, release, replication, dashboard, owner. Trừ điểm nếu dùng heading kiểu \
mẫu như "Mở đầu", "Kết luận", "Tổng quan" một cách máy móc.
3. **Concision & Density** (0-10): Bài có cô đọng không? Trừ điểm mạnh nếu: \
có đoạn lặp lại ý đã nói ở section khác; có câu đệm không thêm dữ kiện mới; \
anecdote cá nhân quá dài (> 3–4 câu); section nào có thể rút ngắn một nửa mà \
không mất ý chính; có câu giải thích rườm rà dù có thể viết đơn giản hơn. \
Target: 800–1400 từ. Bài > 1500 từ mà không phải deep-dive thì tối đa 7 điểm \
cho tiêu chí này.
4. **Formatting** (0-10): YAML frontmatter có đúng chuẩn Astro (publishDate, title, \
excerpt, image, category, tags, author, references)? Markdown structure hợp lý?

Score tổng = trung bình 4 tiêu chí. Passed nếu score >= {_PASS_THRESHOLD}.

Trả về JSON sau (CHỈ JSON, không có text khác):
{{
  "score": <float 0-10>,
  "passed": <true hoặc false>,
  "factual_score": <float>,
  "tone_score": <float>,
  "concision_score": <float>,
  "formatting_score": <float>,
  "feedback": "<danh sách điểm cần sửa cụ thể, hoặc 'Approved' nếu passed>"
}}

---
BÀI VIẾT CẦN REVIEW:

{draft}
"""

    req_chars = len(_REVIEW_SYSTEM) + len(user_message)
    est_tokens = req_chars // 4
    print(
        f"[Review] Calling {get_model_label()} | "
        f"~{est_tokens:,} input tokens ({req_chars:,} chars)"
    )

    raw_text, usage = call_llm(
        system=_REVIEW_SYSTEM,
        user=user_message,
        max_tokens=1024,
        temperature=0.2,
    )
    in_tok = usage.get("inputTokens", "?")
    out_tok = usage.get("outputTokens", "?")
    print(f"[Review] Response: input={in_tok} tok, output={out_tok} tok")

    raw = raw_text.strip()

    # Extract JSON — đề phòng model wrap trong code block
    json_match = re.search(r"\{.*\}", raw, re.DOTALL)
    if json_match:
        try:
            result = json.loads(json_match.group())
        except json.JSONDecodeError:
            result = {"score": 0.0, "passed": False, "feedback": raw}
    else:
        result = {"score": 0.0, "passed": False, "feedback": raw}

    score = float(result.get("score", 0.0))
    passed = score >= _PASS_THRESHOLD

    new_revision_count = revision_count + 1
    status = "✅ PASSED" if passed else f"❌ FAILED (score={score:.1f}/10)"
    print(
        f"[Review] Round {new_revision_count}: {status} -- "
        f"Factual={result.get('factual_score', '?')}, "
        f"Tone={result.get('tone_score', '?')}, "
        f"Concision={result.get('concision_score', '?')}, "
        f"Formatting={result.get('formatting_score', '?')}"
    )
    if not passed:
        print(f"[Review] Feedback: {result.get('feedback', '')[:200]}")

    return {
        "review_score": score,
        "review_passed": passed,
        "review_feedback": result.get("feedback", ""),
        "revision_count": new_revision_count,
    }
