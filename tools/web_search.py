# tavily tool
from tavily import TavilyClient
from config import TAVILY_API_KEY

_client = TavilyClient(api_key=TAVILY_API_KEY)

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

def web_search(query: str)-> str:
    """Execute the search and return a clean text summary."""
    try:
        result = _client.search(
            query=query,
            search_depth="basic",
            max_results=5,
            include_answer=True,
        )
         # Return the AI-generated answer + top source URLs
        answer = result.get("answer","")
        sources = "\n".join(
            f"- {r['url']}: {r['content'][:200]}"
            for r in result.get("results",[])[:3]
        )
        return f"{answer}\n\nSources:\n{sources}" if answer else sources
    except Exception as e:
        return f"Search failed: {e}"