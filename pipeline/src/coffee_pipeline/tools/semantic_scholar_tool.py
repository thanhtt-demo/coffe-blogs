import time

import httpx

_SS_API = "https://api.semanticscholar.org/graph/v1/paper/search"
_MIN_YEAR = 2018
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 5  # seconds, exponential: 5s → 10s → 20s


def search_semantic_scholar(topic: str, limit: int = 5) -> list[dict]:
    """Tìm kiếm papers có peer-review trên Semantic Scholar (free, no key needed).

    Tự động retry với exponential backoff khi bị rate limit (429).
    """
    params = {
        "query": f"coffee {topic}",
        "fields": "title,abstract,url,year,paperId",
        "limit": limit * 3,  # over-fetch để filter theo year
    }

    print(f"[SemanticScholar] GET {_SS_API} | params={params}")
    for attempt in range(_MAX_RETRIES):
        try:
            with httpx.Client(timeout=20.0) as client:
                r = client.get(_SS_API, params=params)

            if r.status_code == 429:
                # Respect Retry-After header nếu có, fallback sang exponential backoff
                retry_after = r.headers.get("Retry-After")
                delay = int(retry_after) if retry_after and retry_after.isdigit() \
                    else _RETRY_BASE_DELAY * (2 ** attempt)
                print(
                    f"[SemanticScholar] Rate limited (429), "
                    f"retry {attempt + 1}/{_MAX_RETRIES} in {delay}s..."
                )
                time.sleep(delay)
                continue

            r.raise_for_status()
            data = r.json()

            total_raw = len(data.get("data", []))
            print(f"[SemanticScholar] Response: {r.status_code} | raw={total_raw} papers")
            results = []
            for paper in data.get("data", []):
                year = paper.get("year") or 0
                if year < _MIN_YEAR:
                    continue
                abstract = paper.get("abstract") or ""
                if not abstract:
                    continue
                paper_id = paper.get("paperId", "")
                url = paper.get("url") or f"https://www.semanticscholar.org/paper/{paper_id}"
                results.append(
                    {
                        "title": paper["title"],
                        "url": url,
                        "abstract": abstract,
                        "source": "semantic_scholar",
                    }
                )
                if len(results) >= limit:
                    break

            print(f"[SemanticScholar] Returning {len(results)} papers after year/abstract filter")
            return results

        except httpx.HTTPStatusError as e:
            print(f"[SemanticScholar] HTTP error: {e}")
            return []
        except Exception as e:
            print(f"[SemanticScholar] Error: {e}")
            return []

    print("[SemanticScholar] Max retries reached, skipping")
    return []
