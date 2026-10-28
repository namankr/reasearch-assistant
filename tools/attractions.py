from tools.web_search import web_search

ATTRACTIONS_TOOL = {
    "name": "search_attractions",
    "description": (
        "Search for the top tourist attractions at a destination. "
        "Returns short summaries of popular places to visit."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "destination": {"type": "string", "description": "City or area e.g. Manali"},
        },
        "required": ["destination"]
    }
}


def search_attractions(destination: str) -> str:
    """Reuses the configured web search provider (ddgs default, Tavily optional)."""
    return web_search(f"top tourist attractions things to do in {destination}")
