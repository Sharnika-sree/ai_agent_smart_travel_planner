"""
MCP Tool Client wrappers for Smart Trip Planner agents.
Provides unified access to MCP tools with clean return types and error safety.
"""

from typing import List, Dict, Any, Optional
import mcp_server

def search_flights(origin: str, destination: str, date: str = "") -> List[Dict[str, Any]]:
    """
    Calls the search_flights tool.
    """
    try:
        return mcp_server.search_flights(origin=origin, destination=destination, date=date)
    except Exception as e:
        return [{
            "id": "FL-ERR",
            "origin": origin,
            "destination": destination,
            "date": date,
            "airline": "Demo Airline (Offline Fallback)",
            "departure": "10:00",
            "arrival": "16:00",
            "price": 25000,
            "currency": "INR",
            "source": f"Fallback error recovery: {str(e)}",
            "is_mock": True
        }]

def search_hotels(
    destination: str,
    check_in: str = "",
    check_out: str = "",
    max_price_per_night: Optional[float] = None
) -> List[Dict[str, Any]]:
    """
    Calls the search_hotels tool.
    """
    try:
        return mcp_server.search_hotels(
            destination=destination,
            check_in=check_in,
            check_out=check_out,
            max_price_per_night=max_price_per_night
        )
    except Exception as e:
        return [{
            "id": "HT-ERR",
            "destination": destination,
            "hotel_name": "Standard Demo Hotel (Offline Fallback)",
            "rating": 4.0,
            "price_per_night": 6000,
            "currency": "INR",
            "category": "standard",
            "amenities": ["Wi-Fi", "Breakfast"],
            "source": f"Fallback error recovery: {str(e)}",
            "is_mock": True
        }]

def convert_currency(amount: float, from_currency: str, to_currency: str) -> Dict[str, Any]:
    """
    Calls the convert_currency tool.
    """
    try:
        return mcp_server.convert_currency(amount, from_currency, to_currency)
    except Exception as e:
        return {
            "converted_amount": round(amount, 2),
            "rate": 1.0,
            "from_currency": from_currency,
            "to_currency": to_currency,
            "source": f"Fallback rate (Error: {str(e)})",
            "is_fallback": True
        }

def get_cheaper_hotels(destination: str, current_price_per_night: float) -> List[Dict[str, Any]]:
    """
    Finds cheaper hotel alternatives compared to the current hotel price.
    Useful for Use Case 4 ("Suggest cheaper hotel options").
    """
    all_hotels = search_hotels(destination=destination)
    cheaper = [h for h in all_hotels if h.get("price_per_night", 999999) < current_price_per_night]
    return sorted(cheaper, key=lambda x: x.get("price_per_night", 0))
