import httpx

_OPENALEX_API = "https://api.openalex.org/works"
_MIN_YEAR = 2018
# Polite pool: thêm email để tăng rate limit lên 100k req/ngày
_MAILTO = "coffee-pipeline@blog.local"


def search_openalex(topic: str, limit: int = 5) -> list[dict]:
    """Tìm kiếm papers peer-reviewed trên OpenAlex (free, 100k req/ngày).

    Thay thế SemanticScholar — không bị rate limit, trả về full abstract.
    """
    params = {
        "search": f"coffee {topic}",
        "filter": f"from_publication_date:{_MIN_YEAR}-01-01,has_abstract:true",
        "select": "id,title,abstract_inverted_index,primary_location,publication_year",
        "sort": "relevance_score:desc",
        "per-page": limit * 2,  # over-fetch để lọc bỏ null
        "mailto": _MAILTO,
    }
    print(f"[OpenAlex] GET {_OPENALEX_API} | query='coffee {topic}' limit={limit}")

    try:
        with httpx.Client(timeout=20.0) as client:
            r = client.get(_OPENALEX_API, params=params)
        r.raise_for_status()
        data = r.json()

        raw_count = len(data.get("results", []))
        print(f"[OpenAlex] Response 200 | raw={raw_count} works")

        results = []
        for work in data.get("results", []):
            title = work.get("title") or ""
            if not title:
                continue

            # Reconstruct abstract from inverted index
            abstract = _reconstruct_abstract(work.get("abstract_inverted_index"))
            if not abstract:
                continue

            # Best available URL
            loc = work.get("primary_location") or {}
            url = (
                (loc.get("landing_page_url") or "")
                or work.get("id", "")  # OpenAlex canonical URL
            )

            results.append(
                {
                    "title": title,
                    "url": url,
                    "abstract": abstract,
                    "source": "openalex",
                }
            )
            if len(results) >= limit:
                break

        print(f"[OpenAlex] Returning {len(results)} papers after filter")
        return results

    except httpx.HTTPStatusError as e:
        print(f"[OpenAlex] HTTP {e.response.status_code}: {e}")
        return []
    except Exception as e:
        print(f"[OpenAlex] Error: {e}")
        return []


def _reconstruct_abstract(inverted_index: dict | None) -> str:
    """OpenAlex stores abstracts as inverted index {word: [positions]}.
    Reconstruct ordered text from it.
    """
    if not inverted_index:
        return ""
    try:
        words: dict[int, str] = {}
        for word, positions in inverted_index.items():
            for pos in positions:
                words[pos] = word
        return " ".join(words[i] for i in sorted(words))
    except Exception:
        return ""
