"""
Minimal test UI for the travel planner (stdlib only).

  python ui_server.py            # http://127.0.0.1:8000
  python ui_server.py --port 9000

Live mode (default) uses the real agents, Google Calendar included: confirm creates an
all-day event. Demo mode uses canned data and ZERO LLM/API calls. The page shows
how many LLM calls have been spent (happy path = ~2: intent parse + structuring).
"""
import argparse
import json
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

import llm_counter
from agent import booker, coordinator
from agent.travel_pipeline import handle_user_message
from chat.service import ChatService
from schemas.travel import FlightOption, HotelOption, ResearchResult, TravelIntent

PROJECT_ID = "travel_agent"
INDEX = Path(__file__).parent / "ui" / "index.html"

_live = {
    "parse": coordinator._parse_travel_intent,
    "calendar": coordinator._calendar,
    "research": coordinator._research,
    "booker_calendar": booker._calendar,
}


class _DemoCalendar:
    """Reports a conflict when the request mentions 'busy' so the conflict path is testable."""
    busy = False

    def check_conflicts(self, start, end):
        if self.busy:
            return {"has_conflict": True,
                    "events": [{"title": "Quarterly review", "start": start, "end": end}]}
        return {"has_conflict": False, "events": []}

    def create_event(self, title, start_date, end_date, description=""):
        return {"id": "demo", "link": None}


_demo_calendar = _DemoCalendar()


def _demo_parse(request: str) -> TravelIntent:
    _demo_calendar.busy = "busy" in request.lower()
    return TravelIntent(origin="Delhi", destination="Goa",
                        start_date="2026-11-06", end_date="2026-11-08")


def _demo_research(intent, user_request, session_id, allow_parallel) -> ResearchResult:
    direct_only = "direct" in user_request.lower()
    flights = [FlightOption(airline="IndiGo", origin="Delhi", destination="Goa",
                            departure="2026-11-06 07:00", arrival="2026-11-06 09:40",
                            price_usd=120, duration_hr=2.7, stops=0)]
    if not direct_only:
        flights.append(FlightOption(airline="Air India", origin="Delhi", destination="Goa",
                                    departure="2026-11-06 06:00", arrival="2026-11-06 11:30",
                                    price_usd=85, duration_hr=5.5, stops=1))
    return ResearchResult(
        destination="Goa", travel_dates="2026-11-06 to 2026-11-08", flights=flights,
        hotels=[HotelOption(name="Seaside Resort", location="Baga", price_usd_per_night=45,
                            rating=4.4, amenities=["wifi", "pool"],
                            check_in="2026-11-06", check_out="2026-11-08")],
        attractions=["Baga Beach", "Fort Aguada", "Dudhsagar Falls"], raw_notes="demo data")


def set_mode(demo: bool) -> None:
    coordinator._parse_travel_intent = _demo_parse if demo else _live["parse"]
    coordinator._calendar = _demo_calendar if demo else _live["calendar"]
    coordinator._research = _demo_research if demo else _live["research"]
    booker._calendar = _demo_calendar if demo else _live["booker_calendar"]


def _state(session_id: str) -> dict:
    chat = ChatService(project_id=PROJECT_ID, session_id=session_id)
    return {"session_id": session_id, "status": chat.get_status(),
            "llm_calls": llm_counter.get()}


class Handler(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str = "application/json"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code: int, payload: dict):
        self._send(code, json.dumps(payload).encode())

    def do_GET(self):
        if self.path in ("/", "/index.html"):
            self._send(200, INDEX.read_bytes(), "text/html; charset=utf-8")
        elif self.path == "/api/state":
            self._json(200, {"llm_calls": llm_counter.get()})
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path != "/api/chat":
            return self._json(404, {"error": "not found"})
        try:
            length = int(self.headers.get("Content-Length", 0))
            body = json.loads(self.rfile.read(length) or b"{}")
            message = (body.get("message") or "").strip()
            if not message:
                return self._json(400, {"error": "message is required"})
            sid = body.get("session_id") or str(uuid.uuid4())
            set_mode(bool(body.get("demo")))
            try:
                reply = handle_user_message(message, sid)
                error = None
            except Exception as e:
                reply, error = f"Request failed: {e}", str(e)
            chat = ChatService(project_id=PROJECT_ID, session_id=sid)
            chat.save_message("user", message)
            chat.save_message("assistant", reply)
            self._json(200, {"reply": reply, "error": error, **_state(sid)})
        except Exception as e:
            self._json(500, {"error": str(e)})

    def log_message(self, fmt, *args):
        pass


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    port = parser.parse_args().port
    print(f"Travel agent UI: http://127.0.0.1:{port}  (Ctrl+C to stop)")
    HTTPServer(("127.0.0.1", port), Handler).serve_forever()


if __name__ == "__main__":
    main()
