"""Unit tests cho tools — mỗi tool được test riêng với mock để không gọi API thật."""
from unittest.mock import MagicMock, patch

import pytest


# ─── ArXiv Tool ───────────────────────────────────────────────────────────────


def test_search_arxiv_returns_expected_shape():
    from coffee_pipeline.tools.arxiv_tool import search_arxiv

    mock_paper = MagicMock()
    mock_paper.title = "Coffee Brewing Kinetics"
    mock_paper.entry_id = "https://arxiv.org/abs/2401.12345"
    mock_paper.summary = "We study the extraction of coffee compounds..."

    with patch("arxiv.Client") as mock_client:
        mock_client.return_value.results.return_value = iter([mock_paper])
        results = search_arxiv("brewing")

    assert isinstance(results, list)
    assert len(results) == 1
    assert results[0]["source"] == "arxiv"
    assert results[0]["title"] == "Coffee Brewing Kinetics"
    assert "abstract" in results[0]


def test_search_arxiv_returns_empty_on_error():
    from coffee_pipeline.tools.arxiv_tool import search_arxiv

    with patch("arxiv.Client", side_effect=Exception("network error")):
        results = search_arxiv("brewing")

    assert results == []


# ─── Semantic Scholar Tool ────────────────────────────────────────────────────


def test_semantic_scholar_filters_old_papers():
    from coffee_pipeline.tools.semantic_scholar_tool import search_semantic_scholar

    mock_response = {
        "data": [
            {"title": "Old Paper 2010", "abstract": "text", "year": 2010, "paperId": "1"},
            {"title": "New Paper 2022", "abstract": "text", "year": 2022, "paperId": "2"},
            {"title": "No Abstract", "abstract": None, "year": 2023, "paperId": "3"},
        ]
    }
    mock_http = MagicMock()
    mock_http.__enter__ = lambda s: s
    mock_http.__exit__ = MagicMock(return_value=False)
    mock_http.get.return_value.json.return_value = mock_response
    mock_http.get.return_value.raise_for_status = MagicMock()

    with patch("httpx.Client", return_value=mock_http):
        results = search_semantic_scholar("caffeine")

    titles = [r["title"] for r in results]
    assert "Old Paper 2010" not in titles
    assert "New Paper 2022" in titles
    assert "No Abstract" not in titles


def test_semantic_scholar_returns_empty_on_error():
    from coffee_pipeline.tools.semantic_scholar_tool import search_semantic_scholar

    with patch("httpx.Client", side_effect=Exception("timeout")):
        results = search_semantic_scholar("caffeine")

    assert results == []


# ─── YouTube Tool ─────────────────────────────────────────────────────────────


def test_youtube_get_video_id():
    from coffee_pipeline.tools.youtube_tool import get_youtube_video_id

    assert get_youtube_video_id("https://www.youtube.com/watch?v=dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert get_youtube_video_id("https://youtu.be/dQw4w9WgXcQ") == "dQw4w9WgXcQ"
    assert get_youtube_video_id("https://example.com/no-video") is None


def test_youtube_trusted_channels_sorted_first():
    from coffee_pipeline.tools.youtube_tool import search_youtube

    mock_entries = [
        {"id": "aaa", "title": "Random video", "channel": "random channel"},
        {"id": "bbb", "title": "James Hoffmann V60", "channel": "james hoffmann"},
    ]
    mock_info = {"entries": mock_entries}

    with patch("yt_dlp.YoutubeDL") as mock_ydl:
        mock_ydl.return_value.__enter__.return_value.extract_info.return_value = mock_info
        results = search_youtube("V60")

    assert len(results) > 0
    # Trusted channel phải ở đầu
    assert results[0]["trusted"] is True


def test_youtube_returns_empty_on_error():
    from coffee_pipeline.tools.youtube_tool import search_youtube

    with patch("yt_dlp.YoutubeDL", side_effect=Exception("network")):
        results = search_youtube("V60")

    assert results == []


# ─── Graph Routing ────────────────────────────────────────────────────────────


def test_review_decision_passes_when_score_high():
    from coffee_pipeline.graph import _review_decision

    state = {
        "review_passed": True,
        "revision_count": 1,
    }
    assert _review_decision(state) == "end"


def test_review_decision_stops_at_max_revisions():
    from coffee_pipeline.graph import _review_decision

    state = {
        "review_passed": False,
        "revision_count": 3,  # >= 3 → end
    }
    assert _review_decision(state) == "end"


def test_review_decision_continues_when_failing():
    from coffee_pipeline.graph import _review_decision

    state = {
        "review_passed": False,
        "revision_count": 1,
    }
    assert _review_decision(state) == "draft"


# ─── Filename derivation ──────────────────────────────────────────────────────


def test_derive_filename_from_frontmatter():
    from coffee_pipeline.cli import _derive_filename

    draft = "---\ntitle: 'Khoa Học Rang Cà Phê'\n---\n\nNội dung..."
    filename = _derive_filename(draft, "fallback")
    assert filename.endswith(".md")
    assert "khoa" in filename.lower()
    assert "rang" in filename.lower()


def test_derive_filename_fallback_to_topic():
    from coffee_pipeline.cli import _derive_filename

    draft = "No frontmatter here"
    filename = _derive_filename(draft, "V60 Brew Ratio")
    assert filename.endswith(".md")
    assert "v60" in filename.lower()


def test_localize_markdown_images_rewrites_cover_and_inline_images(tmp_path, monkeypatch):
    from coffee_pipeline.local_images import localize_markdown_images

    def fake_download(_url: str):
        return (b"image-bytes", ".jpg")

    monkeypatch.setattr("coffee_pipeline.local_images._download_image", fake_download)

    markdown = (
        "---\n"
        "title: 'Demo post'\n"
        "image: 'https://images.unsplash.com/photo-abc123?fm=jpg'\n"
        "---\n\n"
        "![inline](https://images.unsplash.com/photo-def456?fm=jpg)\n"
    )

    localized, summary = localize_markdown_images(markdown, "demo-post", public_dir=tmp_path)

    assert "image: '/images/posts/demo-post/cover.jpg'" in localized
    assert "imageSourceId: 'photo-abc123'" in localized
    assert "![inline](/images/posts/demo-post/inline-01.jpg)" in localized
    assert summary == {"downloaded": 2, "rewritten": 2}
    assert (tmp_path / "images" / "posts" / "demo-post" / "cover.jpg").exists()
    assert (tmp_path / "images" / "posts" / "demo-post" / "inline-01.jpg").exists()


def test_localize_markdown_images_leaves_local_content_unchanged(tmp_path, monkeypatch):
    from coffee_pipeline.local_images import localize_markdown_images

    def fail_download(_url: str):
        raise AssertionError("download should not be called")

    monkeypatch.setattr("coffee_pipeline.local_images._download_image", fail_download)

    markdown = (
        "---\n"
        "title: 'Demo post'\n"
        "image: '/images/posts/demo-post/cover.jpg'\n"
        "imageSourceId: 'photo-abc123'\n"
        "---\n\n"
        "![inline](/images/posts/demo-post/inline-01.jpg)\n"
    )

    localized, summary = localize_markdown_images(markdown, "demo-post", public_dir=tmp_path)

    assert localized == markdown
    assert summary == {"downloaded": 0, "rewritten": 0}
