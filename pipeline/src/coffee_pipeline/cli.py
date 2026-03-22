import json
import os
import re
import sys
from pathlib import Path

import click
from dotenv import load_dotenv
from slugify import slugify


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
    "--category",
    required=True,
    type=click.Choice(["nguon-goc", "rang-xay", "pha-che", "nghien-cuu"]),
    help="Category slug",
)
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
def research(topic: str, category: str, output: str, dry_run: bool) -> None:
    """Nghien cuu chu de va tao bai blog moi."""
    if dry_run:
        os.environ["PIPELINE_DRY_RUN"] = "1"
        _echo("[DRY RUN] Bedrock calls bi skip")

    output_dir = Path(output)
    output_dir.mkdir(parents=True, exist_ok=True)

    _echo(f"Topic    : {topic}")
    _echo(f"Category : {category}")
    _echo(f"Output   : {output_dir.resolve()}")
    _echo("")

    # Import o day de tranh import overhead khi chi dung --help
    from .graph import build_graph

    graph = build_graph()

    initial_state = {
        "topic": topic,
        "category": category,
        "search_results": [],
        "extracted_docs": [],
        "draft_post": "",
        "review_feedback": "",
        "review_score": 0.0,
        "review_passed": False,
        "revision_count": 0,
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
    output_path = output_dir / filename

    output_path.write_text(draft, encoding="utf-8")

    score = final_state.get("review_score", 0.0)
    revisions = final_state.get("revision_count", 0)
    passed = final_state.get("review_passed", False)

    # Save outline + images to cache dir (sources/docs already saved by extract_node)
    _save_pipeline_cache(topic, final_state)

    _echo("")
    _echo("[DONE] Hoan thanh!")
    _echo(f"  File     : {output_path}")
    _echo(f"  Score    : {score:.1f}/10 ({'passed' if passed else 'max revisions reached'})")
    _echo(f"  Revisions: {revisions}")
    _echo(f"  Size     : {len(draft):,} chars")
    _echo("\nMo Astro dev server va truy cap /blog de xem bai viet moi.")


def _save_pipeline_cache(topic: str, final_state: dict) -> None:
    """Luu outline, images, draft ra pipeline/cache/<slug>/ sau khi pipeline xong."""
    try:
        cache_dir = Path(__file__).parent.parent.parent.parent / "cache" / slugify(topic, max_length=60)
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


def _strip_code_fence(text: str) -> str:
    """Strip ```yaml / ``` code fence wrapper that some models add around the output."""
    text = text.strip()
    # Remove leading ```yaml or ``` or ```markdown
    text = re.sub(r'^```[a-z]*\n?', '', text)
    # Remove trailing ```
    text = re.sub(r'\n?```\s*$', '', text)
    return text.strip()


def _derive_filename(draft: str, fallback_topic: str) -> str:
    """Tao filename slug tu title trong frontmatter."""
    match = re.search(r"title:\s*['\"]?(.+?)['\"]?\s*$", draft, re.MULTILINE)
    title = match.group(1).strip() if match else fallback_topic
    slug = slugify(title, max_length=80)
    return f"{slug}.md"
