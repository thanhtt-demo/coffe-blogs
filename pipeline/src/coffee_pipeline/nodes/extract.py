import json
import os
from pathlib import Path

from ..state import ResearchState
from ..tools.crawl4ai_tool import crawl_url_sync
from ..tools.youtube_tool import get_youtube_video_id

# Per-source soft cap (~3k words): bài ngắn lấy hết, bài quá dài cắt tại đây
MAX_PER_SOURCE = 15_000
# Total budget tất cả sources: Claude 3.5 Sonnet có 200k token context
TOTAL_BUDGET = 80_000

# Thư mục cache — 2 cấp trên thư mục này → pipeline/cache/
_CACHE_ROOT = Path(__file__).parent.parent.parent.parent / "cache"


def _cache_dir(topic: str) -> Path:
    from slugify import slugify
    slug = slugify(topic, max_length=60)
    return _CACHE_ROOT / slug


def extract_node(state: ResearchState) -> dict:
    """Node 2: Extract nội dung từ danh sách nguồn tài liệu.

    - ArXiv / OpenAlex → dùng abstract sẵn có (không cần crawl lại)
    - YouTube → youtube-transcript-api (phụ đề, không xem video)
    - Web URL → Crawl4AI (headless browser, trả về fit_markdown)

    Cache: lưu extracted_docs + search_results vào disk sau khi chạy.
    """
    topic = state["topic"]
    search_results = state["search_results"]
    docs: list[dict] = []
    total_chars = 0

    # --- crawl URLs ---
    for item in search_results:
        if total_chars >= TOTAL_BUDGET:
            print(f"[Extract] Total budget {TOTAL_BUDGET} chars reached, skipping rest")
            break

        source_type = item.get("source", "web")

        if source_type in ("arxiv", "semantic_scholar"):
            content = (item.get("abstract") or "")[:MAX_PER_SOURCE]
            if not content:
                continue
            docs.append(
                {
                    "title": item["title"],
                    "url": item["url"],
                    "content": content,
                    "source_type": source_type,
                }
            )
            total_chars += len(content)

        elif source_type == "youtube":
            content = _get_transcript(item)
            if not content:
                print(f"[Extract] YouTube skip (no transcript): {item.get('title', '')}")
                continue
            content = content[:MAX_PER_SOURCE]
            docs.append(
                {
                    "title": item["title"],
                    "url": item["url"],
                    "content": content,
                    "source_type": "youtube",
                }
            )
            total_chars += len(content)

        else:
            # Generic web URL
            print(f"[Extract] Crawling: {item['url']}")
            content = crawl_url_sync(item["url"])
            if not content:
                print(f"[Extract] Crawl empty: {item['url']}")
                continue
            content = content[:MAX_PER_SOURCE]
            docs.append(
                {
                    "title": item.get("title", item["url"]),
                    "url": item["url"],
                    "content": content,
                    "source_type": "web",
                }
            )
            total_chars += len(content)

    print(
        f"[Extract] {len(docs)} sources extracted, "
        f"total {total_chars:,} chars (~{total_chars // 4:,} tokens)"
    )

    # --- persist cache to disk ---
    _save_cache(topic, search_results, docs)

    return {"extracted_docs": docs}


def _get_transcript(item: dict) -> str:
    """Lấy phụ đề YouTube. Trả về chuỗi rỗng nếu không có transcript.

    Hỗ trợ youtube-transcript-api v1.x (instance-based API với FetchedTranscript).
    """
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        video_id = item.get("video_id") or get_youtube_video_id(item.get("url", ""))
        if not video_id:
            return ""

        # v1.x: instance method, returns FetchedTranscript with .to_raw_data()
        api = YouTubeTranscriptApi()
        fetched = api.fetch(video_id, languages=["vi", "en"])
        entries = fetched.to_raw_data()
        return " ".join(entry["text"] for entry in entries)
    except Exception:
        return ""


def _save_cache(topic: str, search_results: list[dict], docs: list[dict]) -> None:
    """Lưu search_results và extracted_docs ra disk tại pipeline/cache/<slug>/."""
    try:
        cache_dir = _cache_dir(topic)
        cache_dir.mkdir(parents=True, exist_ok=True)

        (cache_dir / "sources.json").write_text(
            json.dumps(search_results, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        (cache_dir / "docs.json").write_text(
            json.dumps(docs, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"[Extract] Cache saved → {cache_dir}")
    except Exception as e:
        print(f"[Extract] Cache save failed (non-fatal): {e}")
