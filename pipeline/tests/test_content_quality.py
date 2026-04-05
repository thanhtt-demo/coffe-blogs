"""Tests cho pipeline content quality improvements.

Property-based tests (hypothesis) và unit tests cho:
- Outline Node: thesis field
- Draft Node: thesis-aware prompt, reference filter
- Extract Node: LLM relevance filter
- Review Node: 2 tiêu chí mới
"""

from unittest.mock import MagicMock, patch

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st


class TestReplaceReferencesInDraft:
    """Unit tests for _replace_references_in_draft integration (Task 5.3)."""

    def test_replaces_references_block_with_filtered_docs(self):
        """When draft has a references block, it should be replaced with LLM-filtered docs."""
        from coffee_pipeline.nodes.draft import _replace_references_in_draft

        draft = (
            "---\n"
            "title: 'Test'\n"
            "references:\n"
            "  - title: 'Old Ref 1'\n"
            "    url: 'http://old1.com'\n"
            "    source: 'web'\n"
            "  - title: 'Old Ref 2'\n"
            "    url: 'http://old2.com'\n"
            "    source: 'arxiv'\n"
            "---\n"
            "\n## Content here\n"
        )
        docs = [
            {"title": "Relevant Doc", "url": "http://relevant.com", "source_type": "web", "content": "..."},
            {"title": "Irrelevant Doc", "url": "http://irrelevant.com", "source_type": "arxiv", "content": "..."},
        ]

        # Mock _filter_references_llm to return only the first doc
        with patch(
            "coffee_pipeline.nodes.draft._filter_references_llm",
            return_value=[docs[0]],
        ):
            result = _replace_references_in_draft(draft, docs, "cà phê")

        assert "Relevant Doc" in result
        assert "Old Ref 1" not in result
        assert "Old Ref 2" not in result
        assert "## Content here" in result

    def test_keeps_draft_when_no_references_block(self):
        """When draft has no references block, return draft as-is."""
        from coffee_pipeline.nodes.draft import _replace_references_in_draft

        draft = (
            "---\n"
            "title: 'Test'\n"
            "author: 'Ba Tê'\n"
            "---\n"
            "\n## Content here\n"
        )
        docs = [{"title": "Doc", "url": "http://doc.com", "source_type": "web", "content": "..."}]

        result = _replace_references_in_draft(draft, docs, "cà phê")
        assert result == draft

    def test_keeps_draft_when_no_frontmatter(self):
        """When draft has no YAML frontmatter, return draft as-is."""
        from coffee_pipeline.nodes.draft import _replace_references_in_draft

        draft = "Just some text without frontmatter"
        docs = [{"title": "Doc", "url": "http://doc.com", "source_type": "web", "content": "..."}]

        result = _replace_references_in_draft(draft, docs, "cà phê")
        assert result == draft

    def test_replaces_empty_references_block(self):
        """When draft has references: [], it should be replaced with filtered docs."""
        from coffee_pipeline.nodes.draft import _replace_references_in_draft

        draft = (
            "---\n"
            "title: 'Test'\n"
            "references: []\n"
            "---\n"
            "\n## Content\n"
        )
        docs = [
            {"title": "Good Doc", "url": "http://good.com", "source_type": "web", "content": "..."},
        ]

        with patch(
            "coffee_pipeline.nodes.draft._filter_references_llm",
            return_value=[docs[0]],
        ):
            result = _replace_references_in_draft(draft, docs, "cà phê")

        assert "Good Doc" in result
        assert "references: []" not in result
