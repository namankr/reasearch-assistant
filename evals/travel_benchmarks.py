import re

# Each benchmark runs `turns` in one fresh session; checks run on the LAST response
# and the final session status. `expected` keywords are matched case-insensitively
# (all must appear) except for conflict_detection, where they are informational only.
TRAVEL_BENCHMARKS = [
    {"id": "t01", "turns": ["Book a trip to Goa from Delhi this weekend"],
     "expected": ["flight", "hotel", "total"],
     "checks": ["has_flight_results", "has_hotel_results", "awaiting_approval_set"],
     "category": "full_pipeline"},
    {"id": "t02", "turns": ["I need to fly to Mumbai on Friday for a meeting"],
     "expected": [],
     "checks": ["conflict_or_itinerary"],
     "category": "conflict_detection"},
    {"id": "t03", "turns": ["Find me a budget hotel in Jaipur under 3000 rupees per night"],
     "expected": ["jaipur", "hotel"],
     "checks": ["hotel_price_in_range_usd_40", "correct_destination:jaipur"],
     "category": "hotel_search"},
    {"id": "t04", "turns": ["What are the top attractions in Manali?"],
     "expected": ["manali", "attraction"],
     "checks": ["correct_destination:manali"],
     "category": "attractions"},
    {"id": "t05", "turns": ["Plan a 3-day trip to Udaipur next month"],
     "expected": ["itinerary", "flight", "hotel"],
     "checks": ["awaiting_approval_set"],
     "category": "full_pipeline"},
    {"id": "t06", "turns": ["Plan a weekend trip from Delhi to Jaipur", "cancel"],
     "expected": ["cancelled"],
     "checks": ["status_is:cancelled"],
     "category": "cancellation"},
    {"id": "t07", "turns": ["Plan a weekend trip from Delhi to Jaipur", "edit: prefer direct flights only"],
     "expected": ["itinerary"],
     "checks": ["awaiting_approval_set"],
     "category": "edit_flow"},
    {"id": "t08", "turns": ["Plan a weekend trip from Delhi to Goa", "confirm"],
     "expected": ["confirmed"],
     "checks": ["status_is:completed"],
     "category": "approval"},
    {"id": "t09", "turns": ["Plan a weekend trip from Delhi to Goa", "maybe?"],
     "expected": ["confirm", "cancel", "edit"],
     "checks": ["awaiting_approval_set"],
     "category": "approval_guard"},
    {"id": "t10", "turns": ["Flights and hotels from Mumbai to Goa next Saturday for 2 nights"],
     "expected": ["goa", "flight", "hotel"],
     "checks": ["has_flight_results", "has_hotel_results", "correct_destination:goa"],
     "category": "parallel_results"},
]


def _check_one(name: str, response: str, status: str) -> bool:
    text = response.lower()
    if name == "has_flight_results":
        return "flight (" in text and "$" in response
    if name == "has_hotel_results":
        return "hotel (" in text and "/night" in text
    if name == "awaiting_approval_set":
        return status == "awaiting_approval"
    if name == "conflict_or_itinerary":
        return "calendar event" in text or status == "awaiting_approval"
    if name.startswith("status_is:"):
        return status == name.split(":", 1)[1]
    if name.startswith("correct_destination:"):
        return name.split(":", 1)[1] in text
    if name.startswith("hotel_price_in_range_usd_"):
        limit = float(name.rsplit("_", 1)[1])
        prices = [float(p) for p in re.findall(r"\$([\d.]+)/night", response)]
        return bool(prices) and min(prices) <= limit
    raise ValueError(f"Unknown check: {name}")


def evaluate(bench: dict, response: str, status: str) -> dict:
    lowered = response.lower()
    missing = [k for k in bench["expected"] if k.lower() not in lowered]
    failed = [c for c in bench["checks"] if not _check_one(c, response, status)]
    return {"passed": not missing and not failed, "missing_keywords": missing,
            "failed_checks": failed}
