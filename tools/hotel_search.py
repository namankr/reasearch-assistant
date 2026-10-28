from serpapi import GoogleSearch
from config import SERPAPI_KEY

HOTEL_SEARCH_TOOL = {
    "name": "search_hotels",
    "description": (
        "Search for hotels at a destination for specific dates. "
        "Returns hotel options with names, locations, price estimates, and ratings."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "destination": {"type": "string", "description": "City or area to search hotels in"},
            "check_in":    {"type": "string", "description": "Check-in date YYYY-MM-DD"},
            "check_out":   {"type": "string", "description": "Check-out date YYYY-MM-DD"},
            "budget":      {"type": "string", "description": "Budget preference: budget/mid-range/luxury"},
        },
        "required": ["destination", "check_in", "check_out"]
    }
}


def search_hotels(destination: str, check_in: str,
                  check_out: str, budget: str = "mid-range") -> str:
    """
    Search Google Hotels via SerpAPI.
    Returns structured text the agent can parse into HotelOption objects.
    """
    try:
        params = {
            "engine":      "google_hotels",
            "q":           f"{budget} hotels in {destination}",
            "check_in_date":  check_in,
            "check_out_date": check_out,
            "currency":    "USD",
            "hl":          "en",
            "gl":          "us",
            "api_key":     SERPAPI_KEY,
        }

        search  = GoogleSearch(params)
        results = search.get_dict()

        hotels = results.get("properties", [])

        if not hotels:
            print(f"[Tool] search_hotels: no results for {destination}")
            return (f"No hotel data found for {destination} "
                    f"({check_in} to {check_out}). "
                    f"Please estimate based on typical {budget} options.")

        lines = [f"{budget.title()} hotels in {destination} "
                 f"({check_in} to {check_out}):\n"]

        for h in hotels[:5]:   # top 5
            name       = h.get("name", "Unknown Hotel")
            rating     = h.get("overall_rating", "N/A")
            price      = h.get("rate_per_night", {}).get("lowest", "N/A")
            location   = h.get("neighborhood", destination)
            amenities  = h.get("amenities", [])[:5]
            check_in_t = h.get("check_in_time",  "N/A")
            check_out_t= h.get("check_out_time", "N/A")

            lines.append(
                f"- {name} | "
                f"Location: {location} | "
                f"Rating: {rating}/5 | "
                f"Price: {price}/night | "
                f"Check-in: {check_in_t} | "
                f"Check-out: {check_out_t} | "
                f"Amenities: {', '.join(amenities) if amenities else 'N/A'}"
            )

        print(f"[Tool] search_hotels: found {len(hotels)} hotels in {destination}")
        return "\n".join(lines)

    except Exception as e:
        print(f"[Tool] search_hotels error: {e}")
        return (f"Hotel search failed for {destination}: {e}. "
                f"Please use estimated values.")