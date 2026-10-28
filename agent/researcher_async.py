import asyncio
import json

from agent.llm_utils import generate_json
from agent.react_agent import get_memory
from cache.cache_manager import CacheManager
from config import MAX_TOOL_OUTPUT_CHARS, TRAVEL_CONCURRENCY, TRAVEL_TOOL_TIMEOUT_S
from schemas.travel import ResearchResult, TravelIntent
from security.sanitiser import sanitise
from tools.attractions import search_attractions
from tools.flight_search import search_flights
from tools.hotel_search import search_hotels

PROJECT_ID = "travel_agent"

_cache = None

_STRUCTURE_PROMPT = """Convert these travel search results into ONE JSON object:
{{"destination": str, "travel_dates": str,
  "flights": [{{"airline","origin","destination","departure","arrival","price_usd":float,"duration_hr":float,"stops":int}}],
  "hotels": [{{"name","location","price_usd_per_night":float,"rating":float,"amenities":[str],"check_in","check_out"}}],
  "attractions": [str, up to 5], "raw_notes": str}}
Use only data present in the results; leave a list empty if there is no data for it.
Trip: {origin} -> {destination}, {start} to {end}.

FLIGHTS:
{flights}

HOTELS:
{hotels}

ATTRACTIONS:
{attractions}"""


def _get_cache() -> CacheManager:
    global _cache
    if _cache is None:
        _cache = CacheManager()
    return _cache


def _cache_key(intent: TravelIntent) -> str:
    return (f"travel:{(intent.origin or '').lower()}:{intent.destination.lower()}:"
            f"{intent.start_date}:{intent.end_date}")


async def _guarded(sem: asyncio.Semaphore, fn, *args) -> str:
    """Run a blocking tool in a thread under the shared concurrency cap and a timeout."""
    async with sem:
        return await asyncio.wait_for(asyncio.to_thread(fn, *args), TRAVEL_TOOL_TIMEOUT_S)


async def run_researcher_parallel(intent: TravelIntent, session_id: str) -> ResearchResult:
    """
    Agent A, parallel variant: flights, hotels and attractions are independent given a
    parsed intent, so all three run concurrently. A failed branch degrades to empty
    results instead of failing the whole request.
    """
    key = _cache_key(intent)
    cached = _get_cache().get(key)
    if cached:
        print(f"[Agent A] Cache hit for {key}")
        return ResearchResult(**json.loads(cached))

    sem = asyncio.Semaphore(TRAVEL_CONCURRENCY)
    origin = intent.origin or "unknown"
    flights, hotels, attractions = await asyncio.gather(
        _guarded(sem, search_flights, origin, intent.destination, intent.start_date),
        _guarded(sem, search_hotels, intent.destination, intent.start_date, intent.end_date),
        _guarded(sem, search_attractions, intent.destination),
        return_exceptions=True,
    )

    def clean(name: str, value) -> str:
        if isinstance(value, BaseException):
            print(f"[Agent A] {name} search failed: {value!r}. Continuing without it.")
            return ""
        value = sanitise(value, source=name)
        return value[:MAX_TOOL_OUTPUT_CHARS]

    texts = {n: clean(n, v) for n, v in
             (("flights", flights), ("hotels", hotels), ("attractions", attractions))}
    if not any(texts.values()):
        raise RuntimeError("Agent A failed: all searches failed")

    memory = get_memory(PROJECT_ID)
    for name, text in texts.items():
        if text:
            memory.store(text, source=name, session_id=session_id)

    data = await asyncio.to_thread(
        generate_json,
        _STRUCTURE_PROMPT.format(
            origin=origin, destination=intent.destination,
            start=intent.start_date, end=intent.end_date,
            flights=texts["flights"] or "(none)", hotels=texts["hotels"] or "(none)",
            attractions=texts["attractions"] or "(none)"),
    )
    result = ResearchResult(**data)

    if result.flights or result.hotels:
        _get_cache().store(key, result.model_dump_json())
    return result


def run_researcher_parallel_sync(intent: TravelIntent, session_id: str) -> ResearchResult:
    return asyncio.run(run_researcher_parallel(intent, session_id))
