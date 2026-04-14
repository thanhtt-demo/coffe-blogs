"""Shared utility functions extracted from cli.py.

Both the CLI and the API server import helpers from here so that
logic like filename derivation, code-fence stripping, Prettier
formatting and cache saving lives in exactly one place.
"""

import json
import re
import shutil
import subprocess
from pathlib import Path

from slugify import slugify


def repo_root() -> Path:
    """Return the repository root (four levels up from this file)."""
    return Path(__file__).parent.parent.parent.parent


def strip_code_fence(text: str) -> str:
    """Strip ```yaml / ``` code fence wrapper that some models add around the output."""
    text = text.strip()
    # Remove leading ```yaml or ``` or ```markdown
    text = re.sub(r"^```[a-z]*\n?", "", text)
    # Remove trailing ```
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def derive_filename(draft: str, fallback_topic: str) -> str:
    """Create a filename slug from the title found in frontmatter."""
    match = re.search(r"title:\s*['\"]?(.+?)['\"]?\s*$", draft, re.MULTILINE)
    title = match.group(1).strip() if match else fallback_topic
    slug = slugify(title, max_length=80)
    return f"{slug}.md"


def format_with_prettier(path: Path) -> bool:
    """Format a generated post with Prettier when Node tooling is available."""
    prettier = shutil.which("npx")
    if not prettier:
        return False

    try:
        subprocess.run(
            [prettier, "prettier", "--write", str(path)],
            cwd=repo_root(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


def save_pipeline_cache(topic: str, final_state: dict) -> None:
    """Save outline, images, and draft to pipeline/cache/<slug>/ after pipeline completes."""
    try:
        cache_dir = (
            Path(__file__).parent.parent.parent.parent
            / "cache"
            / slugify(topic, max_length=60)
        )
        cache_dir.mkdir(parents=True, exist_ok=True)

        outline = final_state.get("article_outline")
        if outline:
            (cache_dir / "outline.json").write_text(
                json.dumps(outline, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        images = final_state.get("article_images")
        if images:
            (cache_dir / "images.json").write_text(
                json.dumps(images, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        draft = final_state.get("draft_post", "")
        if draft:
            (cache_dir / "draft.md").write_text(draft, encoding="utf-8")

        print(f"[Cache] Pipeline artifacts saved -> {cache_dir}")
    except Exception as e:
        print(f"[Cache] Save failed (non-fatal): {e}")
