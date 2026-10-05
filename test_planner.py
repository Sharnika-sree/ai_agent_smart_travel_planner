"""
Comprehensive automated tests for Smart Trip Planner:
1. flight MCP tool
2. hotel MCP tool
3. currency conversion fallback
4. RAG retrieval & source attribution
5. budget calculation (pure Python arithmetic)
6. budget exceeded detection
7. conditional re-planning loop (max 2 cycles)
8. missing input validation
9. end-to-end demo workflow (Singapore 4-day under 80k)
"""

import pytest
import mcp_tools
import rag
import currency
import weather
from graph import run_planner, should_replan
from state import TripState

def test_flight_mcp_tool():
    flights = mcp_tools.search_flights(origin="Mumbai", destination="Singapore")
    assert len(flights) > 0
    assert any("Singapore" in f.get("destination", "") for f in flights)
    top = flights[0]
    assert "price" in top
    assert "airline" in top
    assert "currency" in top
    assert "Local demo dataset" in top.get("source", "")

def test_hotel_mcp_tool():
    hotels = mcp_tools.search_hotels(destination="Singapore")
    assert len(hotels) > 0
    assert any("Singapore" in h.get("destination", "") for h in hotels)
    top = hotels[0]
    assert "price_per_night" in top
    assert "hotel_name" in top
    assert "category" in top

def test_currency_conversion_fallback():
    # Convert SGD to INR
    res = currency.convert_currency(100.0, "SGD", "INR")
    assert res["converted_amount"] > 0
    assert res["from_currency"] == "SGD"
    assert res["to_currency"] == "INR"
    assert "source" in res
    assert isinstance(res["is_fallback"], bool)

    # Identical currency check
    same = currency.convert_currency(500.0, "INR", "INR")
    assert same["converted_amount"] == 500.0
    assert same["rate"] == 1.0

def test_rag_retrieval_and_sources():
    # Singapore query
    res = rag.get_visa_info("Singapore", "India")
    assert res["has_grounded_data"] is True
    assert "singapore_visa.txt" in res["sources"]
    assert "SG Arrival Card" in res["summary"] or "visa" in res["summary"].lower()
    assert "IMPORTANT VISA NOTICE" in res["disclaimer"]

    # Thailand query
    res_thai = rag.get_visa_info("Thailand", "India")
    assert res_thai["has_grounded_data"] is True
    assert "thailand_visa.txt" in res_thai["sources"]
    assert "exemption" in res_thai["summary"].lower() or "visa" in res_thai["summary"].lower()

def test_budget_calculation_and_exceeded_detection():
    # Test planning with a very tight budget (e.g. ₹20,000 for Singapore)
    result = run_planner(
        origin="Mumbai",
        destination="Singapore",
        start_date="2026-12-10",
        duration_days=4,
        budget=20000.0,
        currency="INR"
    )
    assert result["total_cost"] > 0
    # Should detect budget exceeded and trigger replanning
    assert result["replanning_count"] <= 2
    assert len(result["replanning_history"]) > 0
    # Total cost must be purely calculated sum
    expected_sum = round(
        result["flight_cost"] + result["hotel_cost"] + result["food_cost"] +
        result["transport_cost"] + result["activity_cost"], 2
    )
    assert result["total_cost"] == expected_sum

def test_replanning_route_and_limit():
    state: TripState = {
        "budget_exceeded": True,
        "replanning_count": 0,
        "missing_critical_info": []
    }
    # First check: should replan
    next_node = should_replan(state)
    assert next_node == "replan"

    # Second check: replanning_count = 1
    state["replanning_count"] = 1
    assert should_replan(state) == "replan"

    # Third check: max limit reached (replanning_count = 2)
    state["replanning_count"] = 2
    assert should_replan(state) == "final_summary"

def test_missing_input_validation():
    # Missing destination and budget <= 0
    result = run_planner(
        origin="",
        destination="",
        duration_days=0,
        budget=0.0
    )
    assert len(result.get("missing_critical_info", [])) > 0
    assert "Missing Information" in result.get("final_response", "")

def test_cheaper_hotels_comparison():
    cheaper = mcp_tools.get_cheaper_hotels("Singapore", 10000.0)
    assert len(cheaper) > 0
    for h in cheaper:
        assert h["price_per_night"] < 10000.0

def test_weather_graceful_handling():
    # Far future date (beyond 16 days)
    res_future = weather.get_destination_weather("Singapore", "2026-12-10")
    assert res_future["status"] == "distant_future"
    assert "16-day forecast horizon" in res_future["summary"]
    # Does not fabricate weather
    assert res_future["forecast"] == []

def test_e2e_singapore_demo():
    # "Plan a 4-day trip to Singapore in December under Rs 80,000."
    result = run_planner(
        origin="Mumbai",
        destination="Singapore",
        start_date="2026-12-10",
        duration_days=4,
        budget=80000.0,
        currency="INR",
        passport_country="India"
    )
    assert result["destination"] == "Singapore"
    assert result["duration_days"] == 4
    assert result["budget"] == 80000.0
    # Must have flights, hotel, itinerary, weather, visa info
    assert result["selected_flight"] is not None
    assert result["selected_hotel"] is not None
    assert len(result["itinerary"]) == 4
    assert result["total_cost"] <= 80000.0  # Successfully met after replanning!
    assert len(result["warnings"]) > 0
    assert len(result["rag_sources"]) > 0
    assert "Singapore" in result["final_response"]
