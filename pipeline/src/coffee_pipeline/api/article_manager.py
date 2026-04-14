"""Article management: read, list, update, and delete Markdown articles.

Articles live in ``src/data/post/`` as Markdown files with YAML frontmatter
delimited by ``---`` markers.  This module provides a thin I/O layer that
the REST routes delegate to.
"""

from __future__ import annotations

import shutil
from pathlib import Path

import yaml

from coffee_pipeline.api.models import ArticleFrontmatter, ArticleResponse
from coffee_pipeline.utils import format_with_prettier, repo_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _posts_dir() -> Path:
    """Return the absolute path to ``src/data/post/``."""
    return repo_root() / "src" / "data" / "post"


def _parse_article(path: Path) -> ArticleResponse | None:
    """Parse a single Markdown file into an *ArticleResponse*.

    Returns ``None`` when the file cannot be parsed (corrupt / missing
    frontmatter).
    """
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return None

    parts = text.split("---", 2)
    if len(parts) < 3:
        return None

    try:
        raw_fm = yaml.safe_load(parts[1])
    except yaml.YAMLError:
        return None

    if not isinstance(raw_fm, dict):
        return None

    # Build frontmatter model – let Pydantic coerce / validate.
    try:
        frontmatter = ArticleFrontmatter(**raw_fm)
    except Exception:
        return None

    content = parts[2].strip()
    slug = path.stem

    # Check for a companion draft file.
    has_draft = (path.parent / f"{slug}-draft.md").is_file()

    return ArticleResponse(
        slug=slug,
        frontmatter=frontmatter,
        content=content,
        has_draft=has_draft,
    )


def _write_article(path: Path, frontmatter: ArticleFrontmatter, content: str) -> None:
    """Serialise *frontmatter* + *content* back to a Markdown file."""
    fm_dict = frontmatter.model_dump()
    yaml_str = yaml.dump(
        fm_dict,
        default_flow_style=False,
        allow_unicode=True,
        sort_keys=False,
    )
    path.write_text(f"---\n{yaml_str}---\n\n{content}\n", encoding="utf-8")
    format_with_prettier(path)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class ArticleManager:
    """Stateless helper that operates on the ``src/data/post/`` directory."""

    # -- List ---------------------------------------------------------------

    def list_articles(self, category: str | None = None) -> list[ArticleResponse]:
        """Return all articles, optionally filtered by *category*.

        Results are sorted by ``publishDate`` descending (newest first).
        """
        posts_dir = _posts_dir()
        if not posts_dir.is_dir():
            return []

        articles: list[ArticleResponse] = []
        for md_file in posts_dir.glob("*.md"):
            # Skip companion draft files (e.g. slug-draft.md).
            if md_file.stem.endswith("-draft"):
                continue
            article = _parse_article(md_file)
            if article is None:
                continue
            if category and article.frontmatter.category != category:
                continue
            articles.append(article)

        articles.sort(
            key=lambda a: a.frontmatter.publishDate,
            reverse=True,
        )
        return articles

    # -- Detail -------------------------------------------------------------

    def get_article(self, slug: str) -> ArticleResponse | None:
        """Return a single article by *slug*, or ``None`` if not found."""
        path = _posts_dir() / f"{slug}.md"
        if not path.is_file():
            return None
        return _parse_article(path)

    # -- Update -------------------------------------------------------------

    def update_article(
        self,
        slug: str,
        frontmatter: ArticleFrontmatter,
        content: str,
    ) -> ArticleResponse:
        """Overwrite an existing article's frontmatter and body.

        Raises ``FileNotFoundError`` when the slug does not exist.
        Raises ``ValueError`` when required fields are missing.
        """
        path = _posts_dir() / f"{slug}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Article not found: {slug}")

        # Pydantic already validates ``title`` (min_length=1) at model
        # construction time, but we double-check here for safety.
        if not frontmatter.title or not frontmatter.title.strip():
            raise ValueError("Field 'title' is required")

        _write_article(path, frontmatter, content)

        # Re-read so the caller gets the canonical on-disk representation.
        article = _parse_article(path)
        assert article is not None
        return article

    # -- Delete -------------------------------------------------------------

    def delete_article(self, slug: str) -> bool:
        """Delete an article and its associated assets.

        Removes:
        * ``src/data/post/{slug}.md``
        * ``public/images/posts/{slug}/``
        * ``cache/{slug}/``
        * ``pipeline/cache/{slug}/``

        Returns ``True`` on success, raises ``FileNotFoundError`` if the
        article does not exist.
        """
        path = _posts_dir() / f"{slug}.md"
        if not path.is_file():
            raise FileNotFoundError(f"Article not found: {slug}")

        # Remove the Markdown file.
        path.unlink()

        # Remove companion draft if present.
        draft_path = _posts_dir() / f"{slug}-draft.md"
        if draft_path.is_file():
            draft_path.unlink()

        root = repo_root()

        # Remove image directory.
        img_dir = root / "public" / "images" / "posts" / slug
        if img_dir.is_dir():
            shutil.rmtree(img_dir)

        # Remove cache directories.
        for cache_dir in (root / "cache" / slug, root / "pipeline" / "cache" / slug):
            if cache_dir.is_dir():
                shutil.rmtree(cache_dir)

        return True
