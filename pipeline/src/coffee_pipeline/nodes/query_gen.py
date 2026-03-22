import json
import re

from ..llm import call_llm
from ..state import ResearchState

_SYSTEM_PROMPT = """\
You are a multilingual search query specialist for coffee research.
Given a Vietnamese topic, generate precise search queries in English and Japanese \
that will surface the best academic papers and YouTube videos.

Rules:
- English: use scientific/technical coffee terminology (SCA, specialty, varietals, etc.)
- Japanese: use Japanese coffee terms naturally (コーヒー, スペシャルティ, 焙煎, etc.)
- Queries should be 3–7 words, diverse — cover different angles of the topic
- Do NOT prefix queries with "coffee" unless the topic truly requires it
- Return ONLY valid JSON — no markdown, no explanation, no code fence

Output format (exactly):
{"en": ["query1", "query2", "query3"], "ja": ["クエリ1", "クエリ2", "クエリ3"]}
"""


def _parse_queries(raw: str) -> dict[str, list[str]]:
    """Parse JSON từ LLM output, strip code fence nếu có."""
    text = raw.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        data = json.loads(text)
        return {
            "en": [q for q in data.get("en", []) if isinstance(q, str)][:3],
            "ja": [q for q in data.get("ja", []) if isinstance(q, str)][:3],
        }
    except json.JSONDecodeError:
        return {"en": [], "ja": []}


def query_gen_node(state: ResearchState) -> dict:
    """Node 0: Dùng LLM sinh query tìm kiếm bằng tiếng Anh và tiếng Nhật."""
    topic = state["topic"]
    print(f"[QueryGen] Generating multilingual queries for: {topic!r}")

    text, usage = call_llm(
        system=_SYSTEM_PROMPT,
        user=f"Vietnamese topic: {topic}",
        max_tokens=256,
        temperature=0.3,
    )
    print(f"[QueryGen] Raw output ({usage.get('outputTokens', '?')} tokens): {text!r}")

    parsed = _parse_queries(text)
    en_queries = parsed["en"]
    ja_queries = parsed["ja"]

    if not en_queries:
        en_queries = [topic]
        print("[QueryGen] Warning: no EN queries parsed, falling back to raw topic")

    print(f"[QueryGen] EN: {en_queries}")
    print(f"[QueryGen] JA: {ja_queries}")

    return {"search_queries": en_queries + ja_queries}
