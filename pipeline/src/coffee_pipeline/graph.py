from langgraph.graph import StateGraph, START, END

from .state import ResearchState
from .nodes.query_gen import query_gen_node
from .nodes.research import research_node
from .nodes.extract import extract_node
from .nodes.outline import outline_node
from .nodes.image_fetch import image_fetch_node
from .nodes.draft import draft_node
from .nodes.review import review_node


def _review_decision(state: ResearchState) -> str:
    """Route sau review: tiếp tục sửa hoặc kết thúc."""
    if state.get("review_passed", False) or state.get("revision_count", 0) >= 3:
        return "end"
    return "draft"


def build_graph():
    """Xây dựng và compile LangGraph pipeline."""
    graph = StateGraph(ResearchState)

    graph.add_node("query_gen", query_gen_node)
    graph.add_node("research", research_node)
    graph.add_node("extract", extract_node)
    graph.add_node("outline", outline_node)
    graph.add_node("image_fetch", image_fetch_node)
    graph.add_node("draft", draft_node)
    graph.add_node("review", review_node)

    graph.add_edge(START, "query_gen")
    graph.add_edge("query_gen", "research")
    graph.add_edge("research", "extract")
    graph.add_edge("extract", "outline")
    graph.add_edge("outline", "image_fetch")
    graph.add_edge("image_fetch", "draft")
    graph.add_edge("draft", "review")
    graph.add_conditional_edges(
        "review",
        _review_decision,
        {"draft": "draft", "end": END},
    )

    return graph.compile()
