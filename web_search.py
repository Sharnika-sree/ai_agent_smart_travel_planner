"""
Web search module using Tavily for time-sensitive destination events, festivals, and closures.
Degrades gracefully when TAVILY_API_KEY is missing without pretending a search occurred.
"""

from typing import Dict, Any, List
import requests
from config import TAVILY_API_KEY

def search_destination_events(destination: str, travel_date_str: str = "") -> Dict[str, Any]:
    """
    Searches for upcoming events, festivals, or local advisories using Tavily.
    If TAVILY_API_KEY is not configured or network fails, gracefully returns an unavailable state.
    """
    if not TAVILY_API_KEY or TAVILY_API_KEY.strip() == "":
        return {
            "status": "unavailable",
            "message": "Live web search unavailable (TAVILY_API_KEY is not configured in .env).",
            "events": [],
            "sources": [],
            "search_performed": False
        }

    query = f"{destination} {travel_date_str} festivals events attractions closures travel advisory".strip()

    try:
        payload = {
            "api_key": TAVILY_API_KEY,
            "query": query,
            "search_depth": "basic",
            "include_answer": True,
            "max_results": 4
        }
        resp = requests.post("https://api.tavily.com/search", json=payload, timeout=6)
        
        if resp.status_code == 200:
            data = resp.json()
            results = data.get("results", [])
            answer = data.get("answer", "")
            
            parsed_events: List[Dict[str, Any]] = []
            sources: List[Dict[str, Any]] = []

            for r in results:
                title = r.get("title", "Event / Notice")
                url = r.get("url", "")
                snippet = r.get("content", "")
                parsed_events.append({
                    "title": title,
                    "snippet": snippet,
                    "url": url
                })
                sources.append({
                    "title": title,
                    "url": url,
                    "type": "Tavily Web Search"
                })

            return {
                "status": "available",
                "message": answer or f"Found {len(parsed_events)} current event / advisory records for {destination}.",
                "events": parsed_events,
                "sources": sources,
                "search_performed": True
            }
        else:
            return {
                "status": "unavailable",
                "message": f"Tavily search API responded with status {resp.status_code}.",
                "events": [],
                "sources": [],
                "search_performed": False
            }

    except Exception as e:
        return {
            "status": "unavailable",
            "message": f"Web search could not be completed: {str(e)}",
            "events": [],
            "sources": [],
            "search_performed": False
        }
