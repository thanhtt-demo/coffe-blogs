"""Property-based tests for pipeline integration with user materials.

Tests extract_node directly (not via API) to verify that user materials
are correctly injected, truncated, budget-limited, and empty-filtered.

Validates: Requirements 4.1, 4.3, 4.4, 4.5, 4.7
"""

from __future__ import annotations

import os

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from coffee_pipeline.nodes.extract import MAX_PER_SOURCE, TOTAL_BUDGET, extract_node
from coffee_pipeline.state import ResearchState


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(user_materials: list[dict]) -> ResearchState:
    """Build a minimal ResearchState for testing user materials only."""
    return ResearchState(
        topic="Test topic",
        category="nghien-cuu",
        search_results=[],
        extracted_docs=[],
        draft_post="",
        user_materials=user_materials,
    )


# ---------------------------------------------------------------------------
# Hypothesis strategies
# ---------------------------------------------------------------------------

MATERIAL_NAMES = st.text(
    min_size=1,
    max_size=100,
    alphabet=st.characters(categories=("L", "N", "Z")),
)

TEXT_CONTENT = st.text(min_size=1, max_size=5000)

# Build oversized content by repeating a base string to exceed MAX_PER_SOURCE
OVERSIZED_CONTENT = st.text(min_size=100, max_size=5000).map(
    lambda s: (s * ((MAX_PER_SOURCE // max(len(s), 1)) + 2))[:MAX_PER_SOURCE + 1000]
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _dry_run(monkeypatch):
    """Set PIPELINE_DRY_RUN to avoid LLM calls in _filter_irrelevant_academic."""
    monkeypatch.setenv("PIPELINE_DRY_RUN", "1")


# ---------------------------------------------------------------------------
# Property 8: Text materials injected into extracted_docs
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 8: Text materials injected into extracted_docs


class TestTextMaterialsInjected:
    """Property 8: Text materials injected into extracted_docs — text materials
    xuất hiện trong extracted_docs với source_type "user_material".

    **Validates: Requirements 4.1, 4.3**
    """

    @given(
        names=st.lists(MATERIAL_NAMES, min_size=1, max_size=5),
        contents=st.lists(TEXT_CONTENT, min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_text_materials_injected(self, names, contents):
        # Align lists to the shorter length
        n = min(len(names), len(contents))
        names = names[:n]
        contents = contents[:n]

        materials = [
            {"file_type": "text", "content": c, "name": nm}
            for nm, c in zip(names, contents)
        ]
        state = _make_state(materials)
        result = extract_node(state)
        extracted = result["extracted_docs"]

        user_docs = [d for d in extracted if d["source_type"] == "user_material"]

        # Every non-empty material should appear
        non_empty = [m for m in materials if m["content"].strip()]
        assert len(user_docs) == len(non_empty)

        for doc, mat in zip(user_docs, non_empty):
            assert doc["source_type"] == "user_material"
            assert doc["title"] == mat["name"]
            # Content should be present (possibly truncated)
            assert mat["content"].strip()[:MAX_PER_SOURCE][:len(doc["content"])] == doc["content"][:len(mat["content"].strip()[:MAX_PER_SOURCE])]


# ---------------------------------------------------------------------------
# Property 9: MAX_PER_SOURCE truncation
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 9: MAX_PER_SOURCE truncation


class TestMaxPerSourceTruncation:
    """Property 9: MAX_PER_SOURCE truncation — text > 15k chars bị truncate.

    **Validates: Requirements 4.4**
    """

    @given(
        name=MATERIAL_NAMES,
        content=OVERSIZED_CONTENT,
    )
    @settings(max_examples=100)
    def test_oversized_content_truncated(self, name, content):
        assert len(content) > MAX_PER_SOURCE  # precondition

        materials = [{"file_type": "text", "content": content, "name": name}]
        state = _make_state(materials)
        result = extract_node(state)
        extracted = result["extracted_docs"]

        user_docs = [d for d in extracted if d["source_type"] == "user_material"]
        assert len(user_docs) == 1
        assert len(user_docs[0]["content"]) <= MAX_PER_SOURCE


# ---------------------------------------------------------------------------
# Property 10: TOTAL_BUDGET invariant
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 10: TOTAL_BUDGET invariant


class TestTotalBudgetInvariant:
    """Property 10: TOTAL_BUDGET invariant — tổng extracted_docs ≤ 80k chars.

    **Validates: Requirements 4.5**
    """

    @given(
        materials=st.lists(
            st.tuples(
                MATERIAL_NAMES,
                st.text(min_size=1000, max_size=5000),
            ),
            min_size=3,
            max_size=20,
        ),
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.large_base_example])
    def test_total_budget_respected(self, materials):
        mats = [
            {"file_type": "text", "content": c, "name": nm}
            for nm, c in materials
        ]
        state = _make_state(mats)
        result = extract_node(state)
        extracted = result["extracted_docs"]

        total_chars = sum(len(d["content"]) for d in extracted)
        assert total_chars <= TOTAL_BUDGET


# ---------------------------------------------------------------------------
# Property 11: Empty materials skipped
# ---------------------------------------------------------------------------

# Feature: custom-research-materials, Property 11: Empty materials skipped


class TestEmptyMaterialsSkipped:
    """Property 11: Empty materials skipped — materials rỗng bị bỏ qua,
    không lỗi.

    **Validates: Requirements 4.7**
    """

    @given(
        empty_contents=st.lists(
            st.sampled_from(["", " ", "  ", "\t", "\n", "  \n  "]),
            min_size=1,
            max_size=5,
        ),
        names=st.lists(MATERIAL_NAMES, min_size=1, max_size=5),
    )
    @settings(max_examples=100)
    def test_empty_materials_skipped(self, empty_contents, names):
        n = min(len(empty_contents), len(names))
        empty_contents = empty_contents[:n]
        names = names[:n]

        materials = [
            {"file_type": "text", "content": c, "name": nm}
            for nm, c in zip(names, empty_contents)
        ]
        state = _make_state(materials)

        # Should not raise
        result = extract_node(state)
        extracted = result["extracted_docs"]

        # No user_material entries should appear
        user_docs = [d for d in extracted if d["source_type"] == "user_material"]
        assert len(user_docs) == 0
