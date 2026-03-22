import pytest


@pytest.fixture
def sample_state():
    return {
        "topic": "V60 brew ratio",
        "category": "pha-che",
        "search_results": [],
        "extracted_docs": [],
        "draft_post": "",
        "review_feedback": "",
        "review_score": 0.0,
        "review_passed": False,
        "revision_count": 0,
    }
