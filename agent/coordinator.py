from datetime import date

from agent.llm_utils import generate_json
from agent.researcher import run_researcher
from agent.researcher_async import run_researcher_parallel_sync
from config import ENABLE_PARALLEL_RESEARCH
from integrations.calendar_client import CalendarMCPClient
from schemas.travel import CoordinatorPlan, ResearchResult, TravelIntent

PROJECT_ID = "travel_agent"

_calendar = CalendarMCPClient()

_INTENT_PROMPT = """Today is {today} ({weekday}).
Extract the trip from the request below and reply with ONLY a JSON object:
{{"origin": "city or null", "destination": "city", "start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD"}}
Resolve relative dates ("this weekend", "next Friday") against today's date.
If no end date or duration is given, use a 1-day trip (end_date = start_date).

Request: {request}"""


def _parse_travel_intent(user_request: str) -> TravelIntent:
    today = date.today()
    data = generate_json(_INTENT_PROMPT.format(
        today=today.isoformat(), weekday=today.strftime("%A"), request=user_request))
    intent = TravelIntent(**data)
    if intent.end_date < intent.start_date:
        raise ValueError(f"end_date {intent.end_date} is before start_date {intent.start_date}")
    return intent


def _format_conflict_message(events: list[dict], intent: TravelIntent) -> str:
    lines = [f"You have {len(events)} calendar event(s) between "
             f"{intent.start_date} and {intent.end_date}:"]
    lines += [f"  - {e['title']} ({e['start']} -> {e['end']})" for e in events]
    lines.append("Pick different dates or say so if you want to travel anyway.")
    return "\n".join(lines)


def _research(intent: TravelIntent, user_request: str, session_id: str,
              allow_parallel: bool) -> ResearchResult:
    """Parallel Agent A first; fall back to the sequential ReAct researcher on failure."""
    if ENABLE_PARALLEL_RESEARCH and allow_parallel:
        try:
            return run_researcher_parallel_sync(intent, session_id)
        except Exception as e:
            print(f"[Agent B] Parallel research failed ({e}); falling back to sequential Agent A")
    return run_researcher(request=user_request, session_id=session_id)


def run_coordinator(user_request: str, session_id: str,
                    is_revision: bool = False) -> CoordinatorPlan:
    """
    Agent B: parse intent -> check calendar -> (only if clear) delegate to Agent A.
    Constraints are validated before the expensive research call.
    Revisions carry free-text constraints (e.g. "direct flights only") that only the
    ReAct researcher honours, so they skip the parallel, cached path.
    """
    intent = _parse_travel_intent(user_request)
    print(f"[Agent B] Trip: {intent.origin or '?'} -> {intent.destination}, "
          f"{intent.start_date} to {intent.end_date}")

    calendar_note = ""
    try:
        conflict = _calendar.check_conflicts(intent.start_date, intent.end_date)
    except Exception as e:
        # Fail open: an unconfigured/unavailable calendar must not block research,
        # but the user is told the check did not happen.
        print(f"[Agent B] Calendar check skipped: {e}")
        conflict = {"has_conflict": False, "events": []}
        calendar_note = " (Calendar not checked - Google Calendar unavailable.)"

    if conflict["has_conflict"]:
        print(f"[Agent B] Conflict found: {conflict['events']}")
        return CoordinatorPlan(
            status="conflict",
            conflict_events=conflict["events"],
            research=None,
            message=_format_conflict_message(conflict["events"], intent),
            intent=intent,
        )

    print("[Agent B] Calendar clear. Delegating to Agent A...")
    research = _research(intent, user_request, session_id, allow_parallel=not is_revision)

    return CoordinatorPlan(
        status="ready_for_booking",
        conflict_events=[],
        research=research,
        message="Research complete. Passing to Agent C for itinerary." + calendar_note,
        intent=intent,
    )
