import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import httpx

_FRONTMATTER_RE = re.compile(r"\A---\n(?P<frontmatter>.*?)\n---\n?", re.DOTALL)
_REMOTE_COVER_RE = re.compile(
    r"(?m)^(?P<prefix>image:\s*['\"]?)(?P<url>https?://[^\s'\"]+)(?P<suffix>['\"]?\s*)$"
)
_REMOTE_MARKDOWN_IMAGE_RE = re.compile(r"!\[(?P<alt>[^\]]*)\]\((?P<url>https?://[^)\s]+)\)")
_SOURCE_ID_RE = re.compile(r"(photo-[a-z0-9\-]+)")
_DEFAULT_PUBLIC_DIR = Path(__file__).parent.parent.parent.parent / "public"


def extract_source_id(url: str | None) -> str | None:
    if not url:
        return None

    match = _SOURCE_ID_RE.search(url)
    return match.group(1) if match else url


def _guess_extension(url: str, content_type: str | None) -> str:
    parsed = urlparse(url)
    params = parse_qs(parsed.query)

    for key in ("fm", "format"):
        value = params.get(key, [None])[0]
        if value in {"jpg", "jpeg", "png", "webp", "gif", "svg"}:
            return ".jpg" if value == "jpeg" else f".{value}"

    if content_type:
        normalized = content_type.split(";", 1)[0].strip().lower()
        mapping = {
            "image/jpeg": ".jpg",
            "image/jpg": ".jpg",
            "image/png": ".png",
            "image/webp": ".webp",
            "image/gif": ".gif",
            "image/svg+xml": ".svg",
        }
        if normalized in mapping:
            return mapping[normalized]

    return ".jpg"


def _download_image(url: str) -> tuple[bytes, str]:
    with httpx.Client(follow_redirects=True, timeout=30.0) as client:
        response = client.get(url)
        response.raise_for_status()
        extension = _guess_extension(url, response.headers.get("content-type"))
        return response.content, extension


def _upsert_frontmatter_value(frontmatter: str, key: str, value: str, *, after_key: str | None = None) -> str:
    pattern = re.compile(rf"(?m)^{re.escape(key)}:\s*.*$")
    replacement = f"{key}: '{value}'"
    if pattern.search(frontmatter):
        return pattern.sub(replacement, frontmatter, count=1)

    if after_key:
        anchor_pattern = re.compile(rf"(?m)^(?P<line>{re.escape(after_key)}:\s*.*)$")
        match = anchor_pattern.search(frontmatter)
        if match:
            line = match.group("line")
            return frontmatter.replace(line, f"{line}\n{replacement}", 1)

    return f"{frontmatter}\n{replacement}"


def localize_markdown_images(
    markdown_text: str,
    post_slug: str,
    *,
    public_dir: Path | None = None,
    overwrite: bool = False,
) -> tuple[str, dict[str, int]]:
    frontmatter_match = _FRONTMATTER_RE.match(markdown_text)
    if not frontmatter_match:
        return markdown_text, {"downloaded": 0, "rewritten": 0}

    public_root = public_dir or _DEFAULT_PUBLIC_DIR
    post_public_dir = public_root / "images" / "posts" / post_slug
    web_prefix = f"/images/posts/{post_slug}"
    post_public_dir.mkdir(parents=True, exist_ok=True)

    frontmatter = frontmatter_match.group("frontmatter")
    body = markdown_text[frontmatter_match.end() :]
    downloads: dict[str, str] = {}
    download_count = 0
    rewrite_count = 0
    inline_index = 0

    def ensure_local(url: str, stem: str) -> str:
        nonlocal download_count

        if url in downloads:
            return downloads[url]

        content, extension = _download_image(url)
        destination = post_public_dir / f"{stem}{extension}"
        if overwrite or not destination.exists():
            destination.write_bytes(content)
        download_count += 1

        local_url = f"{web_prefix}/{destination.name}"
        downloads[url] = local_url
        return local_url

    cover_match = _REMOTE_COVER_RE.search(frontmatter)
    if cover_match:
        cover_url = cover_match.group("url")
        cover_local_url = ensure_local(cover_url, "cover")
        cover_source_id = extract_source_id(cover_url) or cover_url
        frontmatter = _REMOTE_COVER_RE.sub(
            lambda match: f"{match.group('prefix')}{cover_local_url}{match.group('suffix')}",
            frontmatter,
            count=1,
        )
        frontmatter = _upsert_frontmatter_value(frontmatter, "imageSourceId", cover_source_id, after_key="image")
        rewrite_count += 1

    def replace_inline(match: re.Match[str]) -> str:
        nonlocal inline_index, rewrite_count

        inline_index += 1
        local_url = ensure_local(match.group("url"), f"inline-{inline_index:02d}")
        rewrite_count += 1
        return f"![{match.group('alt')}]({local_url})"

    updated_body = _REMOTE_MARKDOWN_IMAGE_RE.sub(replace_inline, body)
    updated_markdown = f"---\n{frontmatter}\n---\n\n{updated_body.lstrip()}"
    return updated_markdown, {"downloaded": download_count, "rewritten": rewrite_count}


__all__ = ["extract_source_id", "localize_markdown_images"]