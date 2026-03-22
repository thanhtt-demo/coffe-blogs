import arxiv


def search_arxiv(topic: str, max_results: int = 5) -> list[dict]:
    """Tìm kiếm papers trên ArXiv liên quan đến chủ đề cà phê."""
    query = f"coffee {topic}"
    print(f"[ArXiv] Search | query={query!r} max_results={max_results} sort=Relevance")
    try:
        client = arxiv.Client()
        search = arxiv.Search(
            query=query,
            max_results=max_results,
            sort_by=arxiv.SortCriterion.Relevance,
        )
        results = []
        for paper in client.results(search):
            results.append(
                {
                    "title": paper.title,
                    "url": paper.entry_id,
                    "abstract": paper.summary,
                    "source": "arxiv",
                }
            )
        print(f"[ArXiv] Returning {len(results)} papers")
        return results
    except Exception as e:
        print(f"[ArXiv] Error: {e}")
        return []
