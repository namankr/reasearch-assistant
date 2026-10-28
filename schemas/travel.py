from pydantic import BaseModel
from typing import Optional

class FlightOption(BaseModel):
    airline:     str
    origin:      str
    destination: str
    departure:   str    # ISO datetime string
    arrival:     str
    price_usd:   float
    duration_hr: float
    stops:       int

class HotelOption(BaseModel):
    name:        str
    location:    str
    price_usd_per_night: float
    rating:      float
    amenities:   list[str]
    check_in:    str
    check_out:   str

class ResearchResult(BaseModel):
    destination:  str
    travel_dates: str
    flights:      list[FlightOption]
    hotels:       list[HotelOption]
    attractions:  list[str]
    raw_notes:    str   # freeform notes from web search

class CoordinatorPlan(BaseModel):
    """Phase 7 — returned by Agent B to Agent C"""
    status:           str              # "ready_for_booking" | "conflict"
    conflict_events:  list[dict]
    research:         Optional[ResearchResult]
    message:          str
    intent:           Optional["TravelIntent"] = None


class TravelIntent(BaseModel):
    """Phase 7 - structured trip request parsed from natural language."""
    origin:      Optional[str] = None
    destination: str
    start_date:  str    # YYYY-MM-DD
    end_date:    str    # YYYY-MM-DD


CoordinatorPlan.model_rebuild()
