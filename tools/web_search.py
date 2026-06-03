# web search tool — DuckDuckGo (default) or Tavily (set SEARCH_PROVIDER=tavily)
import truststore
from config import SEARCH_PROVIDER, TAVILY_API_KEY

truststore.inject_into_ssl()  # Use Windows native cert store (handles Zscaler CA)

# ── Tool definition (Gemini function calling format) ──────────────────────

WEB_SEARCH_TOOL = {
    "name": "web_search",
    "description": (
        "Search the web for current information on a topic. "
        "Use this when you need facts, recent events, or data you don't know."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query — be specific and concise."
            }
        },
        "required": ["query"]
    }
}

def _search_ddgs(query: str) -> str:
    from ddgs import DDGS
    with DDGS() as ddgs:
        results = list(ddgs.text(query, max_results=5))
    if not results:
        return "No results found."
    return "\n".join(f"- {r['title']}: {r['body'][:200]}" for r in results)


def _search_tavily(query: str) -> str:
    import requests
    from tavily import TavilyClient
    session = requests.Session()
    client = TavilyClient(api_key=TAVILY_API_KEY, session=session)
    result = client.search(query=query, search_depth="basic", max_results=5, include_answer=True)
    answer = result.get("answer", "")
    sources = "\n".join(
        f"- {r['url']}: {r['content'][:200]}" for r in result.get("results", [])[:3]
    )
    return f"{answer}\n\nSources:\n{sources}" if answer else sources


def web_search(query: str) -> str:
    """Execute the search and return a clean text summary."""
    try:
        if SEARCH_PROVIDER == "tavily":
            return _search_tavily(query)
        return _search_ddgs(query)
    except Exception as e:
        return f"Search failed: {e}"