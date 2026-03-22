from concurrent.futures import ThreadPoolExecutor, as_completed

from ..state import ResearchState
from ..tools.arxiv_tool import search_arxiv
from ..tools.openalex_tool import search_openalex
from ..tools.web_search_tool import search_web
from ..tools.youtube_tool import search_youtube


def research_node(state: ResearchState) -> dict:
    """Node 1: Tìm kiếm tài liệu từ ArXiv, OpenAlex, Web (DuckDuckGo) và YouTube.

    Chạy song song tất cả (query × source). Kết quả:
    - Papers: ArXiv + OpenAlex, dedup by title, top 10
    - Web:    DuckDuckGo, dedup by URL, top 5 (blog/news chuyên ngành)
    - Videos: YouTube, dedup by id, sort by views, top 5
    """
    topic = state["topic"]
    queries: list[str] = state.get("search_queries") or [topic]  # type: ignore[attr-defined]

    print(f"[Research] Running {len(queries)} queries × 4 sources in parallel (ArXiv + OpenAlex + Web + YouTube)...")

    arxiv_results: list[dict] = []
    ss_results: list[dict] = []
    web_results: list[dict] = []
    yt_results: list[dict] = []

    with ThreadPoolExecutor(max_workers=min(len(queries) * 4, 16)) as executor:
        futures: dict = {}
        for q in queries:
            futures[executor.submit(search_arxiv, q, 5)] = ("arxiv", q)
            futures[executor.submit(search_openalex, q, 5)] = ("openalex", q)
            futures[executor.submit(search_web, q, 5)] = ("web", q)
            futures[executor.submit(search_youtube, q, 5)] = ("youtube", q)

        for future in as_completed(futures):
            source, query = futures[future]
            try:
                data = future.result()
            except Exception as e:
                print(f"[Research] {source} ({query!r}) failed: {e}")
                data = []

            if source == "arxiv":
                arxiv_results.extend(data)
            elif source == "openalex":
                ss_results.extend(data)
            elif source == "web":
                web_results.extend(data)
            else:
                yt_results.extend(data)

    # Deduplicate papers by title (ArXiv và OpenAlex có thể overlap)
    seen_titles: set[str] = set()
    papers: list[dict] = []
    for paper in arxiv_results + ss_results:
        title_key = paper["title"].lower().strip()
        if title_key not in seen_titles:
            seen_titles.add(title_key)
            papers.append(paper)

    # Deduplicate web results by URL
    seen_urls: set[str] = set()
    web_deduped: list[dict] = []
    for w in web_results:
        key = w.get("url", "")
        if key and key not in seen_urls:
            seen_urls.add(key)
            web_deduped.append(w)

    # Deduplicate videos by video_id, sort by view_count descending
    seen_ids: set[str] = set()
    videos_deduped: list[dict] = []
    for v in yt_results:
        vid_key = v.get("video_id") or v.get("url", "")
        if vid_key not in seen_ids:
            seen_ids.add(vid_key)
            videos_deduped.append(v)
    videos_deduped.sort(key=lambda x: x.get("view_count", 0), reverse=True)

    papers = papers[:10]
    web_pages = web_deduped[:5]
    videos = videos_deduped[:5]
    all_results = papers + web_pages + videos

    if len(all_results) < 2:
        raise ValueError(
            f"Not enough sources for topic '{topic}'. "
            "Try a more specific English keyword, e.g. 'V60 brew ratio'."
        )

    print(
        f"[Research] Found {len(papers)} papers + {len(web_pages)} web + {len(videos)} videos "
        f"(from {len(queries)} queries)"
    )
    return {"search_results": all_results}
