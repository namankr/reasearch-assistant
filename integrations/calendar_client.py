import os
from datetime import datetime, timedelta


class CalendarMCPClient:
    """
    Google Calendar wrapper exposed to Agent B as a tool (check_calendar_conflicts).
    The Google service is built lazily so importing this module never needs credentials.
    """

    TOOL_DEF = {
        "name": "check_calendar_conflicts",
        "description": "Check Google Calendar for events between two dates. "
                       "Call this before confirming any travel dates.",
        "parameters": {
            "type": "object",
            "properties": {
                "start_date": {"type": "string", "description": "ISO date YYYY-MM-DD"},
                "end_date":   {"type": "string", "description": "ISO date YYYY-MM-DD"},
            },
            "required": ["start_date", "end_date"]
        }
    }

    def __init__(self, credentials_path: str = None, calendar_id: str = None):
        self._creds_path = credentials_path or os.getenv("GOOGLE_CALENDAR_CREDENTIALS")
        self._cal_id = calendar_id or os.getenv("GOOGLE_CALENDAR_ID", "primary")
        self._service = None

    @property
    def configured(self) -> bool:
        return bool(self._creds_path) and os.path.exists(self._creds_path)

    def _get_service(self):
        if self._service is None:
            from google.oauth2.credentials import Credentials
            from googleapiclient.discovery import build
            creds = Credentials.from_authorized_user_file(self._creds_path)
            self._service = build("calendar", "v3", credentials=creds)
        return self._service

    def check_conflicts(self, start_date: str, end_date: str) -> dict:
        """
        Returns {has_conflict, events: [{title, start, end}]} for the inclusive range.
        Raises if the calendar is not configured or the API call fails.
        """
        if not self.configured:
            raise RuntimeError("Google Calendar credentials are not configured")

        # Validates format and makes end_date inclusive
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d") + timedelta(days=1)

        result = self._get_service().events().list(
            calendarId=self._cal_id,
            timeMin=start.strftime("%Y-%m-%dT00:00:00Z"),
            timeMax=end.strftime("%Y-%m-%dT00:00:00Z"),
            singleEvents=True,
            orderBy="startTime",
        ).execute()

        events = [
            {
                "title": e.get("summary", "Untitled"),
                "start": e["start"].get("dateTime", e["start"].get("date")),
                "end":   e["end"].get("dateTime", e["end"].get("date")),
            }
            for e in result.get("items", [])
        ]
        return {"has_conflict": bool(events), "events": events}
