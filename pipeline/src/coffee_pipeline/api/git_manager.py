"""Git operations for publishing articles.

Wraps ``git add / commit / push`` via :func:`subprocess.run` so that
the REST layer can publish an article with a single method call.
On any git failure the original file content is restored.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import yaml

from coffee_pipeline.api.models import PublishResult
from coffee_pipeline.utils import format_with_prettier, repo_root


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _posts_dir() -> Path:
    return repo_root() / "src" / "data" / "post"


def _run_git(*args: str) -> subprocess.CompletedProcess[str]:
    """Run a git command inside the repository root.

    Raises :class:`RuntimeError` when the command exits with a non-zero
    return code.
    """
    result = subprocess.run(
        ["git", *args],
        cwd=str(repo_root()),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

class GitManager:
    """Publish articles by committing and pushing via git."""

    def publish(self, slug: str) -> PublishResult:
        """Set *draft* to ``false``, commit the article + images, and push.

        Steps
        -----
        1. Check that ``git`` is installed.
        2. Read the article file and parse its frontmatter.
        3. Set ``draft: false`` and write the file back.
        4. ``git add`` the article file **and** its images directory.
        5. ``git commit -m "Publish: {title}"``.
        6. ``git push``.

        If any git command fails the original file content is restored and
        a :class:`RuntimeError` is raised with the stderr output.

        Returns a :class:`PublishResult` on success.
        """
        # -- Pre-flight: git available? ------------------------------------
        if shutil.which("git") is None:
            return PublishResult(
                success=False,
                message="Git is not available on this system",
            )

        # -- Locate article ------------------------------------------------
        article_path = _posts_dir() / f"{slug}.md"
        if not article_path.is_file():
            raise FileNotFoundError(f"Article not found: {slug}")

        original_content = article_path.read_text(encoding="utf-8")

        # -- Parse frontmatter ---------------------------------------------
        parts = original_content.split("---", 2)
        if len(parts) < 3:
            raise ValueError("Article has invalid frontmatter")

        try:
            fm = yaml.safe_load(parts[1])
        except yaml.YAMLError as exc:
            raise ValueError(f"Cannot parse frontmatter: {exc}") from exc

        if not isinstance(fm, dict):
            raise ValueError("Frontmatter is not a YAML mapping")

        title = fm.get("title", slug)

        # -- Update draft flag ---------------------------------------------
        fm["draft"] = False
        yaml_str = yaml.dump(
            fm,
            default_flow_style=False,
            allow_unicode=True,
            sort_keys=False,
        )
        article_path.write_text(
            f"---\n{yaml_str}---\n{parts[2]}",
            encoding="utf-8",
        )
        format_with_prettier(article_path)

        # -- Git operations ------------------------------------------------
        images_dir = f"public/images/posts/{slug}/"
        try:
            _run_git("add", str(article_path.relative_to(repo_root())))

            # Add images dir only when it exists on disk.
            images_abs = repo_root() / images_dir
            if images_abs.is_dir():
                _run_git("add", images_dir)

            # Check if there is actually something to commit.
            status = subprocess.run(
                ["git", "diff", "--cached", "--quiet"],
                cwd=str(repo_root()),
                capture_output=True,
                text=True,
            )
            if status.returncode == 0:
                # Nothing staged — article is already up to date.
                return PublishResult(
                    success=False,
                    message="Article already up to date",
                )

            result = _run_git("commit", "-m", f"Publish: {title}")

            # Extract commit hash from output (first line usually contains it).
            commit_hash: str | None = None
            for token in result.stdout.split():
                if len(token) >= 7 and all(c in "0123456789abcdef" for c in token.rstrip("]")):
                    commit_hash = token.rstrip("]")
                    break

            _run_git("push")

            return PublishResult(
                success=True,
                message=f"Published: {title}",
                commit_hash=commit_hash,
            )

        except RuntimeError:
            # Restore original file on any git failure.
            article_path.write_text(original_content, encoding="utf-8")
            raise
