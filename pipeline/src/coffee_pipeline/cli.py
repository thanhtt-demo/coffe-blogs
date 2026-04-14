import os
import sys
from pathlib import Path

import click
from dotenv import load_dotenv

from .local_images import localize_markdown_images
from .utils import (
    derive_filename,
    format_with_prettier,
    repo_root,
    save_pipeline_cache,
    strip_code_fence,
)


def _setup_stdout() -> None:
    """Reconfigure stdout/stderr to UTF-8 on Windows (default cp1252 breaks Vietnamese)."""
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")


def _echo(msg: str) -> None:
    click.echo(msg)


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
    draft = strip_code_fence(draft)

    # Tao filename tu tieu de trong frontmatter
    filename = derive_filename(draft, topic)

    try:
        draft, localization = localize_markdown_images(draft, Path(filename).stem)
    except Exception as e:
        click.secho(f"[FAILED] Khong the localize image: {e}", fg="red", err=True)
        sys.exit(1)

    output_path = output_dir / filename

    output_path.write_text(draft, encoding="utf-8")
    formatted = format_with_prettier(output_path)

    # Save outline + images to cache dir (sources/docs already saved by extract_node)
    save_pipeline_cache(topic, final_state)

    _echo("")
    _echo("[DONE] Hoan thanh!")
    _echo(f"  File     : {output_path}")
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
        formatted = format_with_prettier(post_path)
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
