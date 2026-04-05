import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from slugify import slugify

from .local_images import localize_markdown_images


def _setup_stdout() -> None:
    """Reconfigure stdout/stderr to UTF-8 on Windows (default cp1252 breaks Vietnamese)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _echo(msg: str) -> None:
    click.echo(msg)


def _repo_root() -> Path:
    return Path(__file__).parent.parent.parent.parent


def _format_with_prettier(path: Path) -> bool:
    """Format a generated post with Prettier when Node tooling is available."""
    prettier = shutil.which("npx")
    if not prettier:
        return False

    try:
        subprocess.run(
            [prettier, "prettier", "--write", str(path)],
            cwd=_repo_root(),
            check=True,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return True
    except (OSError, subprocess.CalledProcessError):
        return False


@click.group()
def main() -> None:
    """Ba Te va Ca Phe -- AI Research Pipeline."""
    _setup_stdout()
    load_dotenv()


@main.command()
@click.option("--topic", required=True, help="Chu de bai viet (tieng Viet hoac Anh)")
@click.option(
    "--output",
    default=str(Path(__file__).parent.parent.parent.parent / "src" / "data" / "post"),
    show_default=True,
    help="Thu muc output (mac dinh: ../src/data/post)",
)
@click.option(
    "--dry-run",
    is_flag=True,
    help="Skip Bedrock calls, dung mock LLM response (test pipeline local)",
)
def research(topic: str, output: str, dry_run: bool) -> None:
    """Nghien cuu chu de va tao bai blog moi."""
    if dry_run:
        os.environ["PIPELINE_DRY_RUN"] = "1"
        _echo("[DRY RUN] Bedrock calls bi skip")

    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _echo(f"Topic    : {topic}")
    _echo(f"Output   : {output_dir.resolve()}")
    _echo("")

    # Import o day de tranh import overhead khi chi dung --help
    from .graph import build_graph

    graph = build_graph()

    initial_state = {
        "topic": topic,
        "category": "",
        "search_results": [],
        "extracted_docs": [],
        "draft_post": "",
    }

    _echo(">> Bat dau pipeline...\n")
    try:
        final_state = graph.invoke(initial_state)
    except Exception as e:
        click.secho(f"\n[FAILED] Pipeline that bai: {e}", fg="red", err=True)
        sys.exit(1)

    draft = final_state.get("draft_post", "")
    if not draft:
        click.secho("[FAILED] Pipeline khong tao ra bai viet.", fg="red", err=True)
        sys.exit(1)

    # Strip code fence neu model wrap frontmatter trong ```yaml ... ```
    draft = _strip_code_fence(draft)

    # Tao filename tu tieu de trong frontmatter
    filename = _derive_filename(draft, topic)

    try:
        draft, localization = localize_markdown_images(draft, Path(filename).stem)
    except Exception as e:
        click.secho(f"[FAILED] Khong the localize image: {e}", fg="red", err=True)
        sys.exit(1)

    output_path = output_dir / filename

    output_path.write_text(draft, encoding="utf-8")
    formatted = _format_with_prettier(output_path)

    # Export bản nháp gốc nếu tồn tại
    draft_original = final_state.get("draft_post_original", "")
    draft_original_path = None
    if draft_original:
        draft_original = _strip_code_fence(draft_original)
        draft_original_filename = f"{Path(filename).stem}-draft.md"
        try:
            draft_original, orig_localization = localize_markdown_images(
                draft_original, Path(draft_original_filename).stem
            )
        except Exception as e:
            click.secho(f"[WARN] Khong the localize image cho draft original: {e}", fg="yellow", err=True)
            orig_localization = {"rewritten": 0, "downloaded": 0}
        draft_original_path = output_dir / draft_original_filename
        draft_original_path.write_text(draft_original, encoding="utf-8")
        _format_with_prettier(draft_original_path)

    # Save outline + images to cache dir (sources/docs already saved by extract_node)
    _save_pipeline_cache(topic, final_state)

    _echo("")
    _echo("[DONE] Hoan thanh!")
    _echo(f"  File     : {output_path}")
    if draft_original_path:
        _echo(f"  Draft    : {draft_original_path}")
    _echo(f"  Size     : {len(draft):,} chars")
    _echo(
        f"  Images   : localized {localization['rewritten']} references, downloaded {localization['downloaded']} files"
    )
    if formatted:
        _echo("  Format   : Prettier applied")
    _echo("\nMo Astro dev server va truy cap /blog de xem bai viet moi.")


@main.command("localize-images")
@click.option(
    "--posts-dir",
    default=str(Path(__file__).parent.parent.parent.parent / "src" / "data" / "post"),
    show_default=True,
    help="Thu muc chua bai post can migrate",
)
@click.option("--post", help="Path den file post cu the can localize")
@click.option(
    "--overwrite", is_flag=True, help="Ghi de image local neu file da ton tai"
)
def localize_images(posts_dir: str, post: str | None, overwrite: bool) -> None:
    """Download remote images ve public/images/posts va rewrite markdown sang local path."""
    targets = (
        [Path(post)]
        if post
        else sorted(Path(posts_dir).glob("*.md"))
        + sorted(Path(posts_dir).glob("*.mdx"))
    )

    if not targets:
        _echo("Khong tim thay bai viet nao de migrate.")
        return

    updated_files = 0
    rewritten_total = 0
    downloaded_total = 0

    for post_path in targets:
        original = post_path.read_text(encoding="utf-8")
        updated, summary = localize_markdown_images(
            original, post_path.stem, overwrite=overwrite
        )
        if updated == original:
            continue

        post_path.write_text(updated, encoding="utf-8")
        formatted = _format_with_prettier(post_path)
        updated_files += 1
        rewritten_total += summary["rewritten"]
        downloaded_total += summary["downloaded"]
        suffix = " + formatted" if formatted else ""
        _echo(
            f"[localized] {post_path.name}: {summary['rewritten']} refs, {summary['downloaded']} files{suffix}"
        )

    _echo("")
    _echo(f"[DONE] Updated {updated_files} post(s)")
    _echo(f"  Rewritten : {rewritten_total}")
    _echo(f"  Downloaded: {downloaded_total}")


def _save_pipeline_cache(topic: str, final_state: dict) -> None:
    """Luu outline, images, draft ra pipeline/cache/<slug>/ sau khi pipeline xong."""
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

        draft_original = final_state.get("draft_post_original", "")
        if draft_original:
            (cache_dir / "draft-original.md").write_text(draft_original, encoding="utf-8")

        print(f"[Cache] Pipeline artifacts saved -> {cache_dir}")
    except Exception as e:
        print(f"[Cache] Save failed (non-fatal): {e}")


def _strip_code_fence(text: str) -> str:
    """Strip ```yaml / ``` code fence wrapper that some models add around the output."""
    text = text.strip()
    # Remove leading ```yaml or ``` or ```markdown
    text = re.sub(r"^```[a-z]*\n?", "", text)
    # Remove trailing ```
    text = re.sub(r"\n?```\s*$", "", text)
    return text.strip()


def _derive_filename(draft: str, fallback_topic: str) -> str:
    """Tao filename slug tu title trong frontmatter."""
    match = re.search(r"title:\s*['\"]?(.+?)['\"]?\s*$", draft, re.MULTILINE)
    title = match.group(1).strip() if match else fallback_topic
    slug = slugify(title, max_length=80)
    return f"{slug}.md"
