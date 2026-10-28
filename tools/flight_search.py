from serpapi import GoogleSearch
from config import SERPAPI_KEY

FLIGHT_SEARCH_TOOL = {
    "name": "search_flights",
    "description": (
        "Search for available flights between two cities on specific dates. "
        "Returns real flight options with airlines, times, and price estimates."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "origin":      {"type": "string", "description": "Departure city or airport code e.g. Delhi, DEL"},
            "destination": {"type": "string", "description": "Arrival city or airport code e.g. Goa, GOI"},
            "date":        {"type": "string", "description": "Travel date in YYYY-MM-DD format"},
        },
        "required": ["origin", "destination", "date"]
    }
}


def search_flights(origin: str, destination: str, date: str) -> str:
    """
    Search Google Flights via SerpAPI.
    Returns structured text the agent can parse into FlightOption objects.
    """
    try:
        params = {
            "engine":            "google_flights",
            "departure_id":      origin,
            "arrival_id":        destination,
            "outbound_date":     date,
            "currency":          "USD",
            "hl":                "en",
            "api_key":           SERPAPI_KEY,
        }

        search  = GoogleSearch(params)
        results = search.get_dict()

        # SerpAPI Google Flights returns best_flights and other_flights
        flights = (
            results.get("best_flights", []) +
            results.get("other_flights", [])
        )

        if not flights:
            # Fallback: try as city names if airport code gave no results
            print(f"[Tool] search_flights: no results for {origin}→{destination}, "
                  f"trying fallback")
            return (f"No direct flight data found for {origin} to {destination} "
                    f"on {date}. Please estimate based on typical routes.")

        lines = [f"Flights from {origin} to {destination} on {date}:\n"]

        for f in flights[:5]:   # top 5
            # Each flight is a list of legs
            legs     = f.get("flights", [])
            price    = f.get("price", "N/A")
            duration = f.get("total_duration", 0)
            stops    = len(legs) - 1 if legs else 0

            if legs:
                first_leg = legs[0]
                last_leg  = legs[-1]
                airline   = first_leg.get("airline", "Unknown")
                depart    = first_leg.get("departure_airport", {})
                arrive    = last_leg.get("arrival_airport", {})

                lines.append(
                    f"- Airline: {airline} | "
                    f"From: {depart.get('name', origin)} "
                    f"({depart.get('time', 'N/A')}) | "
                    f"To: {arrive.get('name', destination)} "
                    f"({arrive.get('time', 'N/A')}) | "
                    f"Duration: {duration} min | "
                    f"Stops: {stops} | "
                    f"Price: ${price}"
                )

        print(f"[Tool] search_flights: found {len(flights)} flights "
              f"{origin}→{destination}")
        return "\n".join(lines)

    except Exception as e:
        print(f"[Tool] search_flights error: {e}")
        return (f"Flight search failed for {origin}→{destination} on {date}: {e}. "
                f"Please use estimated values.")