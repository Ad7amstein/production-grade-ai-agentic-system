"""Tavily web search tool for the agent."""

from langchain.tools import tool
from tavily import TavilyClient

from config.settings import settings

_client = TavilyClient(api_key=settings.TAVILY_API_KEY.get_secret_value())  # pylint: disable=no-member


class SearchError(Exception):
    """Raised when a search cannot be completed."""


@tool(parse_docstring=True)
def tavily_search(query: str) -> str:
    """Search the web with Tavily and return the top results as numbered text.

    Args:
        query (str): The search query.

    Returns:
        str: One block per result with its title, URL, and content, or a message that nothing was found.

    Raises:
        SearchError: If the query is empty.
    """
    if not query.strip():
        raise SearchError("Search query must not be empty.")

    results = _client.search(query, max_results=settings.TAVILY_MAX_RESULTS).get("results") or []
    if not results:
        return "No results found."
    return "\n\n".join(
        f"[{i}] {result['title']}\nURL: {result['url']}\n{result['content']}" for i, result in enumerate(results, 1)
    )
