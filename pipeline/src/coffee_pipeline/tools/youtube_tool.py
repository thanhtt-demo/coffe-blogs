import re

import yt_dlp

# Kênh uy tín về specialty coffee — ưu tiên khi sort
_TRUSTED_CHANNELS = {
    "james hoffmann",
    "lance hedrick",
    "onyx coffee lab",
    "scott rao",
    "sprometheus",
    "euroespresso",
    "whole latte love",
    "seattle coffee gear",
}


def search_youtube(topic: str, max_results: int = 5) -> list[dict]:
    """Tìm video YouTube. Ưu tiên video nhiều view, đánh dấu kênh chuyên gia."""
    search_query = f"ytsearch{max_results}:{topic}"
    print(f"[YouTube] Search | query={search_query!r} max_results={max_results}")
    ydl_opts = {
        "quiet": True,
        "no_warnings": True,
        "extract_flat": True,
        "noplaylist": True,
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(search_query, download=False)

        results = []
        for entry in info.get("entries") or []:
            video_id = entry.get("id", "")
            if not video_id:
                continue
            channel = (entry.get("channel") or entry.get("uploader") or "").lower()
            trusted = any(tc in channel for tc in _TRUSTED_CHANNELS)
            view_count = entry.get("view_count") or 0
            results.append(
                {
                    "title": entry.get("title", ""),
                    "url": f"https://www.youtube.com/watch?v={video_id}",
                    "video_id": video_id,
                    "channel": channel,
                    "trusted": trusted,
                    "view_count": view_count,
                    "source": "youtube",
                }
            )

        # Sort by view count descending
        results.sort(key=lambda x: x["view_count"], reverse=True)
        top = results[:max_results]
        trusted_count = sum(1 for r in top if r["trusted"])
        print(
            f"[YouTube] Returning {len(top)} videos "
            f"(trusted={trusted_count}, top views={top[0]['view_count'] if top else 0:,})"
        )
        return top
    except Exception as e:
        print(f"[YouTube] Error: {e}")
        return []


def get_youtube_video_id(url: str) -> str | None:
    """Extract video ID từ YouTube URL."""
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    return match.group(1) if match else None
