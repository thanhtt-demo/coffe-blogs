import re
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from ..state import ResearchState
from ..tools.unsplash_tool import search_unsplash

# Pool size per job — fetch 3 candidates so we can skip already-used ones
_POOL_SIZE = 3

# Posts directory relative to this file: pipeline/src/coffee_pipeline/nodes/ → src/data/post/
_POSTS_DIR = Path(__file__).parent.parent.parent.parent.parent / "src" / "data" / "post"


def _photo_id(url: str) -> str:
    """Extract the Unsplash photo ID from a URL for deduplication.
    
    e.g. https://images.unsplash.com/photo-1762788115507-5af20c95158f?...  →  photo-1762788115507-5af20c95158f
    Falls back to the bare URL if pattern doesn't match.
    """
    m = re.search(r"(photo-[a-z0-9\-]+)", url)
    return m.group(1) if m else url


def _load_existing_covers() -> set[str]:
    """Scan all published posts and collect their cover photo IDs."""
    ids: set[str] = set()
    if not _POSTS_DIR.exists():
        return ids
    for md_file in _POSTS_DIR.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8", errors="ignore")
            m = re.search(r"^image:\s*['\"]?(https?://[^\s'\"]+)", text, re.MULTILINE)
            if m:
                ids.add(_photo_id(m.group(1)))
        except Exception:
            pass
    print(f"[ImageFetch] Loaded {len(ids)} existing cover photo IDs from {_POSTS_DIR}")
    return ids


def _pick_unused(pool: list[dict], used_ids: set[str]) -> dict | None:
    """Return the first photo from pool whose ID is not in used_ids, or None."""
    for photo in pool:
        pid = _photo_id(photo["url"])
        if pid not in used_ids:
            return photo
    return None


def image_fetch_node(state: ResearchState) -> dict:
    """Node 4: Fetch real Unsplash URLs for cover + each section's image query.

    Guarantees:
    - No duplicate images within the same article.
    - Cover image is not reused from any previously published post.

    Returns article_images:
    {
      "cover": {url, alt, photographer} | None,
      "sections": [{url, alt, photographer} | None, ...]  # 1:1 aligned with outline sections
    }
    """
    outline: dict = state.get("article_outline") or {}  # type: ignore[assignment]
    sections: list[dict] = outline.get("sections", [])
    cover_query: str = outline.get("cover_image_query", "")

    # Collect all (key, section_dict) pairs to fetch in parallel.
    fetch_jobs: list[tuple[str, dict]] = []
    if cover_query:
        fetch_jobs.append(("cover", {
            "title": outline.get("title", ""),
            "description": outline.get("description", ""),
            "image_query": cover_query,
        }))
    for i, sec in enumerate(sections):
        if sec.get("image_query") or sec.get("title"):
            fetch_jobs.append((f"section_{i}", sec))

    if not fetch_jobs:
        print("[ImageFetch] No image queries found, skipping")
        return {"article_images": {"cover": None, "sections": [None] * len(sections)}}

    print(f"[ImageFetch] Fetching {len(fetch_jobs)} jobs × {_POOL_SIZE} candidates in parallel...")

    # Fetch pools in parallel
    job_map: dict[str, dict] = {key: sec for key, sec in fetch_jobs}
    pools: dict[str, list[dict]] = {}
    with ThreadPoolExecutor(max_workers=len(fetch_jobs)) as executor:
        futures = {
            executor.submit(search_unsplash, sec, _POOL_SIZE): key
            for key, sec in fetch_jobs
        }
        for future in as_completed(futures):
            key = futures[future]
            try:
                pools[key] = future.result()
            except Exception as e:
                print(f"[ImageFetch] {key!r} fetch failed: {e}")
                pools[key] = []

    # Assign greedily: cover must avoid existing blog covers, sections avoid each other
    existing_covers = _load_existing_covers()
    used_ids: set[str] = set(existing_covers)  # cover also excluded from this set going forward

    # --- Cover ---
    cover: dict | None = None
    if "cover" in pools:
        cover = _pick_unused(pools["cover"], used_ids)
        if cover:
            used_ids.add(_photo_id(cover["url"]))
            print(f"[ImageFetch] ✓ cover → {cover['url'][:70]}...")
        else:
            print(f"[ImageFetch] ✗ cover → all {len(pools['cover'])} candidates already used")

    # --- Sections ---
    section_images: list[dict | None] = []
    for i in range(len(sections)):
        key = f"section_{i}"
        sec = sections[i]
        label = sec.get("heading", key)[:50]
        if key not in pools:
            section_images.append(None)
            continue
        img = _pick_unused(pools[key], used_ids)
        if img:
            used_ids.add(_photo_id(img["url"]))
            section_images.append(img)
            print(f"[ImageFetch] ✓ {key} ({label!r}) → {img['url'][:70]}...")
        else:
            section_images.append(None)
            print(f"[ImageFetch] ✗ {key} ({label!r}) → all candidates already used")

    found = sum(1 for img in ([cover] + section_images) if img)
    total = 1 + len(sections) if cover_query else len(sections)
    print(f"[ImageFetch] Total assigned: {found}/{total} unique images")
    return {"article_images": {"cover": cover, "sections": section_images}}

