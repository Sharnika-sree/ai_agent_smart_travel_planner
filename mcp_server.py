"""
MCP Server for Smart Trip Planner.
Exposes travel tools:
  - search_flights
  - search_hotels
  - convert_currency
Runs via stdio for standard MCP clients or can be imported for in-process execution.
"""

import json
import os
import sys
from pathlib import Path
from mcp.server.mcpserver import MCPServer
from currency import convert_currency as run_convert_currency

# Paths
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

server = MCPServer("SmartTripPlanner")

def load_flights_data() -> list[dict]:
    flights_file = DATA_DIR / "flights.json"
    if flights_file.exists():
        with open(flights_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def load_hotels_data() -> list[dict]:
    hotels_file = DATA_DIR / "hotels.json"
    if hotels_file.exists():
        with open(hotels_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

@server.tool()
def search_flights(origin: str, destination: str, date: str = "") -> list[dict]:
    """
    Search available mock flight options between origin and destination.
    Data is indicative demo data from local dataset.
    """
    flights = load_flights_data()
    orig = origin.strip().lower()
    dest = destination.strip().lower()

    # Exact or substring match
    matches = [
        f for f in flights
        if dest in f.get("destination", "").lower() and (not orig or orig in f.get("origin", "").lower())
    ]

    # If no exact origin match found, match destination to provide available options
    if not matches:
        matches = [f for f in flights if dest in f.get("destination", "").lower()]

    # If still none, return all demo flights
    if not matches:
        matches = flights[:3]

    # Mark data clearly as demo
    result = []
    for item in matches:
        flight_copy = dict(item)
        flight_copy["source"] = "Local demo dataset (data/flights.json)"
        flight_copy["is_mock"] = True
        result.append(flight_copy)

    return result

@server.tool()
def search_hotels(
    destination: str,
    check_in: str = "",
    check_out: str = "",
    max_price_per_night: float = None
) -> list[dict]:
    """
    Search mock hotel options for a destination, optionally filtered by max price per night.
    Data is indicative demo data from local dataset.
    """
    hotels = load_hotels_data()
    dest = destination.strip().lower()

    matches = [h for h in hotels if dest in h.get("destination", "").lower()]
    if not matches:
        # Fallback to all hotels if destination not found
        matches = hotels[:3]

    if max_price_per_night is not None and max_price_per_night > 0:
        matches = [h for h in matches if h.get("price_per_night", 0) <= max_price_per_night]
        if not matches:
            # Sort by price ascending if none strictly under max_price
            matches = sorted(hotels, key=lambda x: x.get("price_per_night", 999999))[:2]

    # Sort by price ascending
    matches = sorted(matches, key=lambda x: x.get("price_per_night", 0))

    result = []
    for item in matches:
        hotel_copy = dict(item)
        hotel_copy["source"] = "Local demo dataset (data/hotels.json)"
        hotel_copy["is_mock"] = True
        result.append(hotel_copy)

    return result

@server.tool()
def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """
    Convert an amount from one currency to another using Frankfurter API with demo fallback.
    """
    return run_convert_currency(amount, from_currency, to_currency)

if __name__ == "__main__":
    # Run stdio MCP server
    server.run(transport="stdio")
