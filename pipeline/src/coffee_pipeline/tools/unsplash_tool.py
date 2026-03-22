import os
import re

import httpx

_UNSPLASH_API = "https://api.unsplash.com/search/photos"

_SYSTEM_PROMPT = (
    "You are a concise image search assistant for Unsplash. "
    "Return ONLY 2-3 short English keywords separated by spaces. "
    "No explanation, no punctuation, no quotes -- just the keywords."
)


def search_unsplash(section: dict, count: int = 1) -> list[dict]:
    """Fetch images from Unsplash using LLM-generated keywords.

    Input `section` is a dict with any of: title, description, image_query.
    Attempt 1: LLM picks best 2-3 English keywords from section content.
    Attempt 2: LLM picks simpler keywords after being told attempt 1 yielded 0 results.

    Requires env var UNSPLASH_ACCESS_KEY.
    Returns list of dicts: [{url, alt, photographer, query}]
    """
    access_key = os.getenv("UNSPLASH_ACCESS_KEY", "").strip()
    if not access_key:
        print("[Unsplash] UNSPLASH_ACCESS_KEY not set -- skipping")
        return []

    context = _build_context(section)

    # Attempt 1
    kw1 = _ask_llm(context, previous=None)
    print(f"[Unsplash] LLM keywords attempt 1: {kw1!r}")
    results = _try_query(kw1, count, access_key)
    if results:
        return results

    # Attempt 2 -- tell LLM that attempt 1 returned nothing
    kw2 = _ask_llm(context, previous=kw1)
    print(f"[Unsplash] LLM keywords attempt 2: {kw2!r}")
    return _try_query(kw2, count, access_key)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _build_context(section: dict) -> str:
    parts = []
    if section.get("title"):
        parts.append(f"Title: {section['title']}")
    if section.get("description"):
        parts.append(f"Description: {section['description']}")
    if section.get("image_query"):
        parts.append(f"Image hint: {section['image_query']}")
    return "\n".join(parts) or str(section)


def _ask_llm(context: str, previous: str | None) -> str:
    from ..llm import call_llm

    if previous:
        user = (
            f"Section content:\n{context}\n\n"
            f"Note: searching Unsplash with '{previous}' returned 0 results.\n"
            "Give simpler, more generic 2-3 English keywords that will definitely find results on Unsplash."
        )
    else:
        user = (
            f"Section content:\n{context}\n\n"
            "Return 2-3 short English keywords to find a matching image on Unsplash."
        )

    text, _ = call_llm(
        system=_SYSTEM_PROMPT,
        user=user,
        max_tokens=30,
        temperature=0.3,
    )
    return text.strip().strip('"').strip("'")


def _try_query(query: str, count: int, access_key: str) -> list[dict]:
    """Single Unsplash API call. Returns [] on 0 results or error."""
    params = {
        "query": query,
        "per_page": max(count, 1),
        "orientation": "landscape",
        "client_id": access_key,
        "content_filter": "high",
    }
    print(f"[Unsplash] GET {_UNSPLASH_API} | query={query!r}")
    try:
        with httpx.Client(timeout=10.0) as client:
            r = client.get(_UNSPLASH_API, params=params)
        r.raise_for_status()
        data = r.json()

        results = []
        for photo in data.get("results", []):
            url = photo.get("urls", {}).get("regular", "")
            if not url:
                continue
            alt = (
                photo.get("alt_description")
                or photo.get("description")
                or query
            )
            photographer = photo.get("user", {}).get("name", "Unsplash")
            results.append(
                {
                    "url": url,
                    "alt": alt.capitalize() if alt else query,
                    "photographer": photographer,
                    "source_id": _extract_source_id(url),
                    "query": query,
                }
            )

        print(f"[Unsplash] {query!r} -> {len(results)} photos returned")
        return results[:count]

    except httpx.HTTPStatusError as e:
        print(f"[Unsplash] HTTP {e.response.status_code} for {query!r}: {e}")
        return []
    except Exception as e:
        print(f"[Unsplash] Error for {query!r}: {e}")
        return []


def _extract_source_id(url: str) -> str:
    match = re.search(r"(photo-[a-z0-9\-]+)", url)
    return match.group(1) if match else url
