from chat.service import ChatService
from integrations.calendar_client import CalendarMCPClient
from schemas.travel import CoordinatorPlan, ResearchResult

PROJECT_ID = "travel_agent"
EDIT_PREFIX = "__EDIT_REQUEST__:"
_calendar = CalendarMCPClient()


def _format_itinerary(research: ResearchResult, nights: int | None = None) -> str:
    lines = [f"ITINERARY - {research.destination} ({research.travel_dates})", ""]

    flight = min(research.flights, key=lambda f: f.price_usd, default=None)
    if flight:
        lines += ["Flight (cheapest option):",
                  f"  {flight.airline}: {flight.origin} -> {flight.destination}",
                  f"  Depart {flight.departure} | Arrive {flight.arrival} | "
                  f"{flight.duration_hr}h, {flight.stops} stop(s) | ${flight.price_usd:.2f}", ""]
    else:
        lines += ["Flight: none found.", ""]

    hotel = max(research.hotels, key=lambda h: h.rating, default=None)
    hotel_total = 0.0
    if hotel:
        hotel_total = hotel.price_usd_per_night * (nights or 1)
        lines += ["Hotel (highest rated):",
                  f"  {hotel.name} - {hotel.location} | {hotel.rating}/5",
                  f"  ${hotel.price_usd_per_night:.2f}/night | "
                  f"{hotel.check_in} -> {hotel.check_out}", ""]
    else:
        lines += ["Hotel: none found.", ""]

    if research.attractions:
        lines.append("Attractions:")
        lines += [f"  {i}. {a}" for i, a in enumerate(research.attractions, 1)]
        lines.append("")

    total = (flight.price_usd if flight else 0.0) + hotel_total
    lines.append(f"Estimated total: ${total:.2f}")
    return "\n".join(lines)


def _nights(research: ResearchResult) -> int:
    from datetime import date
    try:
        h = research.hotels[0]
        return max((date.fromisoformat(h.check_out) - date.fromisoformat(h.check_in)).days, 1)
    except Exception:
        return 1


def run_booker(plan: CoordinatorPlan, session_id: str, original_request: str = "") -> str:
    """
    Agent C: format the itinerary and pause for human approval.
    Nothing is booked here; the session moves to awaiting_approval.
    """
    if plan.research is None:
        raise ValueError("run_booker requires a plan with research results")

    chat = ChatService(project_id=PROJECT_ID, session_id=session_id)
    itinerary = _format_itinerary(plan.research, _nights(plan.research))

    chat.set_context("pending_itinerary", itinerary)
    chat.set_context("research_data", plan.research.model_dump())
    if plan.intent:
        chat.set_context("intent", plan.intent.model_dump())
    if original_request:
        chat.set_context("original_request", original_request)
    chat.set_status("awaiting_approval")

    return (
        f"{itinerary}\n\n---\n"
        "Type **confirm** to proceed with booking.\n"
        "Type **cancel** to start over.\n"
        "Type **edit [your changes]** to revise (e.g. 'edit: prefer direct flights only')"
    )


def _confirm(chat: ChatService) -> str:
    """
    Writes the trip to Google Calendar. On failure the session stays in
    awaiting_approval so the user can fix credentials and type confirm again.
    Flights/hotels are NOT actually booked - there is no booking integration yet.
    """
    intent = chat.get_context("intent")
    itinerary = chat.get_context("pending_itinerary") or ""
    research = chat.get_context("research_data") or {}
    if not intent:
        return "Cannot confirm: trip dates are missing from this session. Please start a new request."

    destination = research.get("destination") or intent["destination"]
    try:
        event = _calendar.create_event(
            title=f"Trip to {destination}",
            start_date=intent["start_date"],
            end_date=intent["end_date"],
            description=itinerary,
        )
    except Exception as e:
        return (f"Could not add the trip to Google Calendar: {e}\n"
                "Fix the problem (see README: Google Calendar setup) and type confirm to retry, "
                "or type cancel.")

    chat.set_context("calendar_event", event)
    chat.set_status("completed")
    link = f"\n{event['link']}" if event.get("link") else ""
    return (f"Confirmed. '{'Trip to ' + destination}' was added to your Google Calendar "
            f"({intent['start_date']} to {intent['end_date']}).{link}\n"
            "NOTE: no flights or hotels were actually purchased - booking APIs are not integrated.")


def handle_approval(user_message: str, session_id: str) -> str:
    """
    Routes confirm / cancel / edit while status == awaiting_approval.
    No agent ever sees these messages.
    """
    chat = ChatService(project_id=PROJECT_ID, session_id=session_id)
    msg = user_message.strip().lower()

    if msg == "confirm":
        return _confirm(chat)

    if msg == "cancel":
        chat.set_status("cancelled")
        return "Trip cancelled. Start a new request whenever you're ready."

    if msg.startswith("edit"):
        instruction = user_message.strip()[4:].lstrip(" :").strip()
        if not instruction:
            return "Please say what to change, e.g. 'edit: prefer direct flights only'."
        chat.set_status("running")
        return f"{EDIT_PREFIX}{instruction}"

    return "Please type confirm, cancel, or edit [your changes] to proceed."
