import threading
import time

from duckduckgo_search import DDGS

# Serialize all DDG calls — parallel queries from research_node would otherwise
# trigger rate limits instantly.
_DDG_LOCK = threading.Lock()

# Ưu tiên các domain uy tín về coffee specialty
_TRUSTED_DOMAINS = {
    "perfectdailygrind.com",
    "sprudge.com",
    "coffeereview.com",
    "scanews.coffee",
    "jimseven.com",
    "baristahustle.com",
    "worldcoffeeresearch.org",
    "ico.org",
    "coffeemag.com",
    "coffeebi.com",
    "ncausa.org",
}

# Loại bỏ các trang thương mại/spam không có nội dung chuyên sâu
_BLOCKED_DOMAINS = {
    "amazon.com", "ebay.com", "aliexpress.com",
    "pinterest.com", "instagram.com", "facebook.com",
}


def search_web(query: str, max_results: int = 5) -> list[dict]:
    """Tìm kiếm bài viết web qua DuckDuckGo (free, no API key).

    Giữ _DDG_LOCK xuyên suốt toàn bộ retry loop — nếu một thread đang retry
    thì các thread khác phải chờ hoàn toàn, tránh cả hai cùng hit rate limit.
    Sau mỗi call thành công ngủ 1.5s để DDG không coi là burst.
    """
    print(f"[WebSearch] Query: {query!r} max={max_results}")
    raw: list[dict] = []
    with _DDG_LOCK:
        delays = [0, 4, 8]  # seconds before each attempt (held inside the lock)
        for attempt, delay in enumerate(delays, start=1):
            if delay:
                time.sleep(delay)
            try:
                with DDGS() as ddgs:
                    raw = list(ddgs.text(query, max_results=max_results * 3))
                time.sleep(1.5)  # post-call cooldown before releasing lock
                break  # success
            except Exception as e:
                err = str(e)
                if "202" in err or "Ratelimit" in err.lower():
                    if attempt < len(delays):
                        print(f"[WebSearch] Rate limited, retrying in {delays[attempt]}s (attempt {attempt}/{len(delays)})...")
                        continue
                print(f"[WebSearch] Error: {e}")
                return []
            return []


    results = []
    trusted = []
    others = []

    for r in raw:
        url = r.get("href", "")
        title = r.get("title", "")
        snippet = r.get("body", "")

        if not url or not title:
            continue

        domain = _extract_domain(url)
        if any(b in domain for b in _BLOCKED_DOMAINS):
            continue

        item = {
            "title": title,
            "url": url,
            "abstract": snippet,
            "source": "web",
        }

        if any(t in domain for t in _TRUSTED_DOMAINS):
            trusted.append(item)
        else:
            others.append(item)

    # Trusted domains first, then others
    results = (trusted + others)[:max_results]
    trusted_count = sum(1 for r in results if _extract_domain(r["url"]) in _TRUSTED_DOMAINS)
    print(f"[WebSearch] Returning {len(results)} results (trusted={trusted_count})")
    return results


def _extract_domain(url: str) -> str:
    try:
        from urllib.parse import urlparse
        return urlparse(url).netloc.lower().removeprefix("www.")
    except Exception:
        return ""
