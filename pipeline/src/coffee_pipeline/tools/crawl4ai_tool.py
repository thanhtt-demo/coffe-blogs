import asyncio
import sys
from concurrent.futures import ThreadPoolExecutor

from crawl4ai import AsyncWebCrawler

# Soft limit per source — bài dài lấy hết, không cắt cứng giữa chừng.
# Claude 3.5 Sonnet có 200k token context, 15k chars ≈ 3k words là hợp lý.
MAX_PER_SOURCE = 15_000


async def crawl_url(url: str) -> str:
    """Crawl một URL và trả về main content dạng Markdown.

    Dùng fit_markdown (loại boilerplate nav/sidebar/footer) nếu available,
    fallback sang raw_markdown nếu không có filter.
    """
    print(f"[Crawl4AI] Crawling {url}")
    try:
        async with AsyncWebCrawler(verbose=False) as crawler:
            result = await crawler.arun(url=url)

        if not result.success:
            return ""

        # Defensive extraction: hỗ trợ nhiều phiên bản crawl4ai
        md = result.markdown
        if isinstance(md, str):
            content = md
        else:
            # crawl4ai 0.4+: markdown là MarkdownGenerationResult object
            fit = getattr(md, "fit_markdown", None)
            raw = getattr(md, "raw_markdown", None)
            content = fit or raw or str(md or "")

        chars = len(content[:MAX_PER_SOURCE])
        print(f"[Crawl4AI] {url} → {chars} chars (limit={MAX_PER_SOURCE})")
        return content[:MAX_PER_SOURCE]
    except Exception as e:
        print(f"[Crawl4AI] Error crawling {url}: {e}")
        return ""


def crawl_url_sync(url: str) -> str:
    """Sync wrapper — chạy crawl trong thread riêng để tránh event loop conflict.

    On Windows, asyncio.run() closes the loop before Playwright subprocess transports
    can clean up, causing harmless but noisy 'Event loop is closed' tracebacks.
    We avoid this by managing the loop lifecycle manually with a short drain period.
    """
    def _run() -> str:
        if sys.platform == "win32":
            loop = asyncio.ProactorEventLoop()
        else:
            loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(crawl_url(url))
        finally:
            # Drain pending callbacks (subprocess transport __del__ cleanup)
            # before closing to suppress 'Event loop is closed' on Windows.
            try:
                loop.run_until_complete(asyncio.sleep(0.25))
            except Exception:
                pass
            loop.close()

    with ThreadPoolExecutor(max_workers=1) as executor:
        return executor.submit(_run).result()
