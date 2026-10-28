import json
from agent.react_agent import run_agent
from chat.service import ChatService
from router.model_router import ModelRouter
from schemas.travel import ResearchResult
from tools.flight_search import search_flights, FLIGHT_SEARCH_TOOL
from tools.hotel_search import search_hotels, HOTEL_SEARCH_TOOL
from tools.attractions import search_attractions, ATTRACTIONS_TOOL
from google.genai import types

PROJECT_ID = "travel_agent"

# ── Travel-specific tool registry ─────────────────────────────────────────
TRAVEL_TOOL_REGISTRY = {
    "search_flights":     search_flights,
    "search_hotels":      search_hotels,
    "search_attractions": search_attractions,
}

# ── Gemini tool declarations for travel tools ─────────────────────────────
def _build_travel_tools():
    declarations = []
    for tool_def in [FLIGHT_SEARCH_TOOL, HOTEL_SEARCH_TOOL, ATTRACTIONS_TOOL]:
        props = {}
        for name, schema in tool_def["parameters"]["properties"].items():
            props[name] = types.Schema(
                type=types.Type.STRING,
                description=schema["description"]
            )
        declarations.append(types.FunctionDeclaration(
            name=tool_def["name"],
            description=tool_def["description"],
            parameters=types.Schema(
                type=types.Type.OBJECT,
                properties=props,
                required=tool_def["parameters"].get("required", [])
            )
        ))
    return [types.Tool(function_declarations=declarations)]


RESEARCHER_PROMPT = """You are Agent A, a travel research specialist.
Given a travel request, use your tools to search for:
  1. Available flights (origin → destination, on travel date)
  2. Hotels at the destination (for the travel dates)
  3. Top 5 attractions at the destination

After gathering information with your tools, return ONLY a JSON object
with this exact structure — no markdown, no explanation:

{
  "destination": "city name",
  "travel_dates": "date range string",
  "flights": [
    {
      "airline": "airline name",
      "origin": "city",
      "destination": "city",
      "departure": "YYYY-MM-DD HH:MM",
      "arrival": "YYYY-MM-DD HH:MM",
      "price_usd": 0.0,
      "duration_hr": 0.0,
      "stops": 0
    }
  ],
  "hotels": [
    {
      "name": "hotel name",
      "location": "area",
      "price_usd_per_night": 0.0,
      "rating": 0.0,
      "amenities": ["wifi", "pool"],
      "check_in": "YYYY-MM-DD",
      "check_out": "YYYY-MM-DD"
    }
  ],
  "attractions": [],
  "raw_notes": "any additional notes"
}

Use realistic estimates if exact prices are unavailable.
Always include at least 2 flights, 2 hotels and up to 5 attractions."""

router = ModelRouter()


def run_researcher(request: str, session_id: str) -> ResearchResult:
    """
    Agent A — researches flights, hotels, attractions.
    Returns a validated ResearchResult — never raw text.
    Raises on parse failure so the coordinator knows it failed.
    """
    chat = ChatService(project_id=PROJECT_ID, session_id=session_id)
    model_name, _ =  router.route(request)

    raw = run_agent(
        user_query=request,
        history=chat.build_context(),
        session_id=session_id,
        project_id=PROJECT_ID,
        model_name=model_name,
        system_prompt_override=RESEARCHER_PROMPT,
        tool_registry_override=TRAVEL_TOOL_REGISTRY,
        gemini_tools_override=_build_travel_tools(),
    )

    # ── Guard: catch agent-level errors before attempting JSON parse ──────
    ERROR_MARKERS = [
        "quota exceeded", "http 429", "rate limit",
        "model request failed", "agent operation failed",
        "max iterations reached", "not_found", "not found",
        "no longer available",
    ]
    if any(marker in raw.lower() for marker in ERROR_MARKERS):
        print(f"[Agent A] Agent returned an error: {raw[:200]}")
        raise RuntimeError(f"Agent A failed: {raw}")
    # Strip markdown fences if model adds them despite instructions
    cleaned = raw.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```")[1]
        if cleaned.startswith("json"):
            cleaned = cleaned[4:]
        cleaned = cleaned.strip()

    try:
        data = json.loads(cleaned)
        result = ResearchResult(**data)
        print(f"[Agent A] Research complete: {len(result.flights)} flights, "
              f"{len(result.hotels)} hotels, {len(result.attractions)} attractions")
        return result
    except json.JSONDecodeError as e:
        print(f"[Agent A] JSON parse failed: {e}\nRaw: {raw[:300]}")
        raise
    except Exception as e:
        print(f"[Agent A] Validation failed: {e}\nRaw: {raw[:300]}")
        raise
