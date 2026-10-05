"""
LangGraph TripState schema.
Maintains the shared state across all planner, itinerary, weather, budget, and summary nodes.
"""

from typing import TypedDict, List, Dict, Any, Optional

class TripState(TypedDict, total=False):
    # Core User Input
    user_request: str
    origin: str
    destination: str
    start_date: str
    end_date: str
    duration_days: int
    budget: float
    currency: str
    passport_country: str

    # Missing Constraints Check
    missing_critical_info: List[str]

    # MCP Booking Tools Data
    flights: List[Dict[str, Any]]
    selected_flight: Optional[Dict[str, Any]]
    hotels: List[Dict[str, Any]]
    selected_hotel: Optional[Dict[str, Any]]

    # Knowledge & RAG
    visa_info: str
    rag_sources: List[Dict[str, Any]]

    # Weather & Live Search
    weather: Dict[str, Any]
    events: List[Dict[str, Any]]
    advisories: List[str]
    web_sources: List[Dict[str, Any]]

    # Itinerary Schedule
    itinerary: List[Dict[str, Any]]

    # Budget Calculation (Pure Python Logic)
    flight_cost: float
    hotel_cost: float
    food_cost: float
    transport_cost: float
    activity_cost: float
    total_cost: float

    # Conditional Replanning
    budget_exceeded: bool
    replanning_count: int
    replanning_history: List[str]

    # Summary & Output
    warnings: List[str]
    final_response: str
    execution_steps: List[str]
