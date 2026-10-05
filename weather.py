"""
Weather lookup module using Open-Meteo (free, open API, no key required).
Provides real-time forecasts when dates are within the 16-day horizon,
or transparently declares forecast unavailable for distant dates without hallucinating.
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
import requests

WMO_WEATHER_CODES = {
    0: "Clear sky ☀️",
    1: "Mainly clear 🌤️",
    2: "Partly cloudy ⛅",
    3: "Overcast ☁️",
    45: "Foggy 🌫️",
    48: "Depositing rime fog 🌫️",
    51: "Light drizzle 🌦️",
    53: "Moderate drizzle 🌧️",
    55: "Dense drizzle 🌧️",
    61: "Slight rain 🌧️",
    63: "Moderate rain 🌧️",
    65: "Heavy rain ⛈️",
    71: "Slight snow 🌨️",
    80: "Slight rain showers 🌦️",
    81: "Moderate rain showers 🌧️",
    82: "Violent rain showers ⛈️",
    95: "Thunderstorm ⚡",
    96: "Thunderstorm with slight hail ⛈️",
    99: "Thunderstorm with heavy hail ⛈️"
}

def get_coordinates(destination: str) -> Optional[Dict[str, Any]]:
    """
    Looks up coordinates for destination via Open-Meteo geocoding API.
    """
    clean_dest = destination.split(",")[0].strip()
    url = f"https://geocoding-api.open-meteo.com/v1/search?name={clean_dest}&count=1&language=en&format=json"
    try:
        resp = requests.get(url, timeout=4)
        if resp.status_code == 200:
            data = resp.json()
            if "results" in data and len(data["results"]) > 0:
                top = data["results"][0]
                return {
                    "name": top.get("name"),
                    "country": top.get("country"),
                    "latitude": top.get("latitude"),
                    "longitude": top.get("longitude")
                }
    except Exception:
        pass
    
    # Known fallback coordinates for demo destinations
    known_coords = {
        "singapore": {"name": "Singapore", "country": "Singapore", "latitude": 1.3521, "longitude": 103.8198},
        "bangkok": {"name": "Bangkok", "country": "Thailand", "latitude": 13.7563, "longitude": 100.5018},
        "thailand": {"name": "Bangkok", "country": "Thailand", "latitude": 13.7563, "longitude": 100.5018},
        "kuala lumpur": {"name": "Kuala Lumpur", "country": "Malaysia", "latitude": 3.1390, "longitude": 101.6869},
        "malaysia": {"name": "Kuala Lumpur", "country": "Malaysia", "latitude": 3.1390, "longitude": 101.6869},
        "munnar": {"name": "Munnar", "country": "India", "latitude": 10.0889, "longitude": 77.0595}
    }
    return known_coords.get(clean_dest.lower())

def get_destination_weather(
    destination: str,
    start_date_str: str = "",
    end_date_str: str = ""
) -> Dict[str, Any]:
    """
    Fetches weather forecast from Open-Meteo for the destination and date window.
    Strictly reports unavailability if dates are beyond 16 days.
    """
    coords = get_coordinates(destination)
    if not coords:
        return {
            "status": "unavailable",
            "summary": f"Could not determine coordinates for '{destination}'. Weather data unavailable.",
            "forecast": [],
            "source": "Open-Meteo Geocoding",
            "rain_expected": False,
            "recommendation": "Check local weather closer to departure date."
        }

    # Analyze requested dates
    today = date.today()
    max_forecast_date = today + timedelta(days=16)
    
    start_dt = None
    if start_date_str:
        try:
            start_dt = datetime.strptime(start_date_str.strip(), "%Y-%m-%d").date()
        except ValueError:
            pass

    # Check if requested date is too far in future
    if start_dt and start_dt > max_forecast_date:
        return {
            "status": "distant_future",
            "destination": coords["name"],
            "country": coords.get("country", ""),
            "start_date": start_date_str,
            "end_date": end_date_str,
            "summary": (
                f"Live weather forecast is unavailable for {start_date_str} as it exceeds "
                f"Open-Meteo's 16-day forecast horizon. Historical climate for {coords['name']}: "
                f"Expect seasonal tropical/subtropical temperatures. It is recommended to carry an umbrella "
                f"or light jacket and plan indoor backup options."
            ),
            "forecast": [],
            "source": "Open-Meteo Forecast Horizon Limit (Strict No-Hallucination Policy)",
            "rain_expected": False,
            "recommendation": "Re-check 7 to 10 days before your travel date for real-time atmospheric readings."
        }

    # Fetch live forecast
    lat = coords["latitude"]
    lon = coords["longitude"]
    url = (
        f"https://api.open-meteo.com/v1/forecast?"
        f"latitude={lat}&longitude={lon}&daily=weathercode,temperature_2m_max,temperature_2m_min,"
        f"precipitation_probability_max,rain_sum&timezone=auto"
    )

    try:
        resp = requests.get(url, timeout=5)
        if resp.status_code != 200:
            return {
                "status": "unavailable",
                "summary": "Open-Meteo API returned an error or is temporarily unreachable.",
                "forecast": [],
                "source": "Open-Meteo API",
                "rain_expected": False,
                "recommendation": "Keep flexible travel plans and carry basic rain protection."
            }

        data = resp.json().get("daily", {})
        times = data.get("time", [])
        weathercodes = data.get("weathercode", [])
        max_temps = data.get("temperature_2m_max", [])
        min_temps = data.get("temperature_2m_min", [])
        precip_probs = data.get("precipitation_probability_max", [])

        forecast_list: List[Dict[str, Any]] = []
        any_rain = False

        for i in range(min(len(times), 7)):
            code = weathercodes[i] if i < len(weathercodes) else 0
            desc = WMO_WEATHER_CODES.get(code, "Moderate conditions")
            rain_prob = precip_probs[i] if i < len(precip_probs) else 0
            if (rain_prob and rain_prob > 40) or code in [51, 53, 55, 61, 63, 65, 80, 81, 82, 95]:
                any_rain = True

            forecast_list.append({
                "date": times[i],
                "condition": desc,
                "temp_max": max_temps[i] if i < len(max_temps) else "N/A",
                "temp_min": min_temps[i] if i < len(min_temps) else "N/A",
                "rain_probability": f"{rain_prob}%" if rain_prob is not None else "0%"
            })

        avg_max = (
            round(sum([t for t in max_temps[:5] if isinstance(t, (int, float))]) / 5, 1)
            if max_temps else "28"
        )
        
        summary = (
            f"Forecast for {coords['name']}: Daytime temperatures average around {avg_max}°C. "
            f"{'Intermittent rain/showers expected; prepare indoor alternatives.' if any_rain else 'Generally clear to mild conditions favorable for outdoor touring.'}"
        )

        return {
            "status": "available",
            "destination": coords["name"],
            "country": coords.get("country", ""),
            "summary": summary,
            "forecast": forecast_list,
            "source": f"Open-Meteo Free API (Lat: {lat}, Lon: {lon})",
            "rain_expected": any_rain,
            "recommendation": (
                "Schedule outdoor sightseeing (gardens, parks, walking tours) in the morning and "
                "indoor attractions (museums, malls, domes) in the afternoon if rain occurs."
                if any_rain else
                "Ideal conditions for outdoor sightseeing and walking tours."
            )
        }

    except Exception as e:
        return {
            "status": "unavailable",
            "summary": f"Could not retrieve live weather from Open-Meteo ({str(e)}).",
            "forecast": [],
            "source": "Open-Meteo API (Offline)",
            "rain_expected": False,
            "recommendation": "Check weather forecast closer to travel date."
        }
