"""
One-time Google OAuth helper. Produces the token file used by CalendarMCPClient.

1. Google Cloud Console -> enable "Google Calendar API", create an OAuth client
   (type: Desktop app), download it as client_secret.json.
2. python google_auth.py client_secret.json
3. Set in .env:
     GOOGLE_CALENDAR_CREDENTIALS=token.json
     GOOGLE_CALENDAR_ID=primary        # or your calendar's email
"""
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

# Read + write events (needed for conflict checks AND creating the trip event)
SCOPES = ["https://www.googleapis.com/auth/calendar.events"]



def main():
    secret = sys.argv[1] if len(sys.argv) > 1 else "client_secret.json"
    out = sys.argv[2] if len(sys.argv) > 2 else "token.json"
    print("Using scopes:", SCOPES)
    creds = InstalledAppFlow.from_client_secrets_file(secret, SCOPES).run_local_server(port=0)
    with open(out, "w") as f:
        f.write(creds.to_json())
    print(f"Saved {out}. Set GOOGLE_CALENDAR_CREDENTIALS={out} in .env")


if __name__ == "__main__":
    main()
