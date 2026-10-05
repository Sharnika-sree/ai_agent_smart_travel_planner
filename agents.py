"""
LangGraph Agent Nodes for Smart Trip Planner:
1. Planner Agent
2. Weather Agent
3. Itinerary Agent
4. Budget Agent
5. Re-plan Agent (Conditional)
6. Final Summary Agent
"""

from datetime import datetime, date, timedelta
from typing import Dict, Any, List, Optional
from config import LLM_API_KEY, LLM_MODEL, ESTIMATED_DAILY_EXPENSES
from state import TripState
import mcp_tools
import rag
import weather as weather_module
import web_search

def _get_daily_rates(destination: str) -> Dict[str, float]:
    dest = destination.lower()
    for key in ESTIMATED_DAILY_EXPENSES:
        if key in dest:
            return ESTIMATED_DAILY_EXPENSES[key]
    return ESTIMATED_DAILY_EXPENSES["default"]

# -------------------------------------------------------------
# 1. PLANNER AGENT
# -------------------------------------------------------------
def planner_node(state: TripState) -> TripState:
    """
    Validates input parameters, checks for missing critical info,
    and fetches initial flight/hotel mock data, RAG visa documents,
    and current web advisories.
    """
    exec_steps = list(state.get("execution_steps", []))
    exec_steps.append("Planner Agent: Validating requirements and fetching initial inventory")

    missing = []
    destination = state.get("destination", "").strip()
    if not destination:
        missing.append("Destination is required.")

    origin = state.get("origin", "").strip()
    if not origin:
        missing.append("Starting location (origin) is required.")

    duration_days = state.get("duration_days", 0)
    if duration_days <= 0:
        # Try inferring from start_date and end_date
        s_date = state.get("start_date", "")
        e_date = state.get("end_date", "")
        if s_date and e_date:
            try:
                d1 = datetime.strptime(s_date, "%Y-%m-%d").date()
                d2 = datetime.strptime(e_date, "%Y-%m-%d").date()
                delta = (d2 - d1).days + 1
                if delta > 0:
                    duration_days = delta
                else:
                    missing.append("End date must be on or after start date.")
            except ValueError:
                duration_days = 4
        else:
            duration_days = 4  # Default fallback duration

    budget = state.get("budget", 0.0)
    if budget <= 0:
        missing.append("A valid budget amount is required.")

    currency = state.get("currency", "INR").upper()
    passport_country = state.get("passport_country", "India")
    start_date = state.get("start_date", "")

    if missing:
        return {
            **state,
            "missing_critical_info": missing,
            "execution_steps": exec_steps,
            "final_response": "### Missing Information\n\nPlease provide the missing details to generate your plan:\n" + "\n".join([f"- {m}" for m in missing])
        }

    # 1. Fetch mock flights via MCP
    flights = mcp_tools.search_flights(origin=origin, destination=destination, date=start_date)
    # Pick a standard/balanced initial flight (e.g., standard or first available)
    selected_flight = None
    if flights:
        standard_flights = [f for f in flights if f.get("tier") == "standard"]
        selected_flight = standard_flights[0] if standard_flights else flights[0]

    # 2. Fetch mock hotels via MCP
    hotels = mcp_tools.search_hotels(destination=destination)
    selected_hotel = None
    if hotels:
        # Start with standard/mid-tier hotel for initial plan
        standard_hotels = [h for h in hotels if h.get("category") in ["standard", "luxury"]]
        selected_hotel = standard_hotels[0] if standard_hotels else hotels[0]

    # 3. Retrieve Visa Info via Local RAG
    visa_res = rag.get_visa_info(destination=destination, passport_country=passport_country)
    visa_info = visa_res.get("summary", "")
    rag_sources = [{"title": f"Official Guidance: {s}", "url": f"knowledge/{s}", "type": "Local RAG Knowledge Base"} for s in visa_res.get("sources", [])]

    # 4. Tavily Web Search for Local Events / Closures
    search_res = web_search.search_destination_events(destination=destination, travel_date_str=start_date)
    events = search_res.get("events", [])
    web_sources = search_res.get("sources", [])

    return {
        **state,
        "origin": origin,
        "destination": destination,
        "duration_days": duration_days,
        "budget": budget,
        "currency": currency,
        "passport_country": passport_country,
        "missing_critical_info": [],
        "flights": flights,
        "selected_flight": selected_flight,
        "hotels": hotels,
        "selected_hotel": selected_hotel,
        "visa_info": visa_info,
        "rag_sources": rag_sources,
        "events": events,
        "web_sources": web_sources,
        "execution_steps": exec_steps,
        "replanning_count": state.get("replanning_count", 0),
        "replanning_history": state.get("replanning_history", [])
    }

# -------------------------------------------------------------
# 2. WEATHER AGENT
# -------------------------------------------------------------
def weather_node(state: TripState) -> TripState:
    """
    Retrieves weather forecast from Open-Meteo and sets weather risk advice.
    """
    exec_steps = list(state.get("execution_steps", []))
    exec_steps.append("Weather Agent: Checking Open-Meteo forecast and atmospheric conditions")

    destination = state.get("destination", "")
    start_date = state.get("start_date", "")
    end_date = state.get("end_date", "")

    weather_data = weather_module.get_destination_weather(destination, start_date, end_date)
    
    advisories = list(state.get("advisories", []))
    if weather_data.get("rain_expected"):
        advisories.append("Weather alert: Showers expected during travel window; scheduled indoor backup attractions.")

    return {
        **state,
        "weather": weather_data,
        "advisories": advisories,
        "execution_steps": exec_steps
    }

# -------------------------------------------------------------
# 3. ITINERARY AGENT
# -------------------------------------------------------------
def itinerary_node(state: TripState) -> TripState:
    """
    Creates a balanced, day-by-day morning, afternoon, and evening schedule
    grounded in the destination, selected hotel, weather, and events.
    """
    exec_steps = list(state.get("execution_steps", []))
    exec_steps.append("Itinerary Agent: Synthesizing day-by-day itinerary")

    destination = state.get("destination", "Singapore")
    duration = state.get("duration_days", 4)
    start_date_str = state.get("start_date", "")
    weather_info = state.get("weather", {})
    rain_expected = weather_info.get("rain_expected", False)
    hotel = state.get("selected_hotel", {})
    hotel_name = hotel.get("hotel_name", "your hotel")
    events = state.get("events", [])
    replan_count = state.get("replanning_count", 0)

    # Base date calculation
    base_date = None
    if start_date_str:
        try:
            base_date = datetime.strptime(start_date_str, "%Y-%m-%d").date()
        except ValueError:
            base_date = date.today() + timedelta(days=14)
    else:
        base_date = date.today() + timedelta(days=14)

    # Curated templates by destination
    dest_key = destination.lower()
    days_data = []

    if "singapore" in dest_key:
        attraction_pool = [
            {
                "day_title": "Arrival & Iconic Marina Bay",
                "morning": "Flight arrival in Singapore (Changi Jewel). Take MRT or taxi to check into " + hotel_name + ". Freshen up.",
                "afternoon": "Stroll around Merlion Park with views of Marina Bay; visit the indoor air-conditioned Flower Dome & Cloud Forest at Gardens by the Bay.",
                "evening": "Watch the Spectra Light & Water Show at Event Plaza followed by the Supertree Grove Garden Rhapsody music and light show.",
                "notes": "Indoor conservatories provide shelter from tropical humidity and showers."
            },
            {
                "day_title": "Cultural Heritage & Chinatown Cuisine",
                "morning": "Explore Chinatown: visit Buddha Tooth Relic Temple, Sri Mariamman Temple, and Chinatown Street Market.",
                "afternoon": "Authentic lunch at Maxwell Food Centre (famous Tian Tian Chicken Rice). Visit Asian Civilisations Museum along the Singapore River.",
                "evening": "Clarke Quay evening walk and scenic Singapore River Cruise. Dinner by the waterfront.",
                "notes": "Comfortable walking shoes recommended. Hawker food is high-quality and budget-friendly."
            },
            {
                "day_title": "Sentosa Island & Tropical Relaxation",
                "morning": "Board Sentosa Express monorail from VivoCity to Resorts World Sentosa. Explore S.E.A. Aquarium.",
                "afternoon": "Relax at Siloso Beach or Palawan Beach; walk across the suspension bridge to the Southernmost Point of Continental Asia.",
                "evening": "Sunset cocktails or dinner at Henderson Waves bridge / Vivocity Sky Park overlooking HarbourFront.",
                "notes": "If replanning for lower cost, replace paid theme park tickets with free scenic boardwalks and public beaches."
            },
            {
                "day_title": "Botanic Gardens, Orchard Road & Departure",
                "morning": "Morning walk through UNESCO World Heritage Singapore Botanic Gardens & National Orchid Garden.",
                "afternoon": "Window shopping along Orchard Road; visit Kampong Glam and Sultan Mosque for artisan souvenirs.",
                "evening": "Head to Changi Airport early to witness the majestic HSBC Rain Vortex at Jewel before departure flight.",
                "notes": "Submit SG Arrival Card (SGAC) 3 days prior to arrival. Keep transit card loaded."
            }
        ]
    elif "bangkok" in dest_key or "thailand" in dest_key:
        attraction_pool = [
            {
                "day_title": "Arrival & Riverside Grandeur",
                "morning": "Arrival at Bangkok (BKK/DMK). Transfer and check into " + hotel_name + ".",
                "afternoon": "Explore the majestic Grand Palace and Emerald Buddha (Wat Phra Kaew).",
                "evening": "Sunset at Wat Arun (Temple of Dawn) across Chao Phraya River, followed by street food at Asiatique The Riverfront.",
                "notes": "Modest clothing covering shoulders and knees required for temple visits."
            },
            {
                "day_title": "Temples & Historic Canals",
                "morning": "Visit Wat Pho (Reclining Buddha) and experience traditional Thai massage.",
                "afternoon": "Long-tail canal boat tour along Thonburi klongs; visit Jim Thompson House Museum.",
                "evening": "Vibrant street food tour in Yaowarat (Chinatown) - sample pad thai, dim sum, and mango sticky rice.",
                "notes": "Negotiate tuk-tuk fares in advance or use BTS/MRT for reliable pricing."
            },
            {
                "day_title": "Markets & Modern City",
                "morning": "Chatuchak Weekend Market (or Pratunam Market on weekdays) for local crafts and apparel.",
                "afternoon": "Shopping and air-conditioned lunch at ICONSIAM (SookSiam indoor floating market).",
                "evening": "Rooftop beverage or dinner overlooking Bangkok's neon skyline.",
                "notes": "Stay hydrated in afternoon heat."
            },
            {
                "day_title": "Green Parks & Departure",
                "morning": "Morning walk and swan boat ride in Lumphini Park.",
                "afternoon": "Souvenir shopping at MBK Center or CentralWorld. Last minute Thai snacks.",
                "evening": "Airport transfer for return flight.",
                "notes": "Allow 3+ hours for airport transit during Bangkok peak traffic hours."
            }
        ]
    elif "munnar" in dest_key:
        attraction_pool = [
            {
                "day_title": "Scenic Ghat Drive & Tea County Arrival",
                "morning": "Arrival via Kochi (COK). Scenic 3.5-hour drive through Cheeyappara & Valara waterfalls into Munnar.",
                "afternoon": "Check in to " + hotel_name + ". Warm welcome with fresh cardamom tea. Walk around Munnar town market.",
                "evening": "Watch a traditional Kathakali dance and Kalaripayattu martial arts performance at Punarjani Cultural Village.",
                "notes": "Winding Ghat roads; carry motion sickness medicine if sensitive."
            },
            {
                "day_title": "Tea Plantations & High Altitude Wildlife",
                "morning": "Early excursion to Eravikulam National Park (Rajamalai) to spot the endangered Nilgiri Tahr.",
                "afternoon": "Guided walk through lush KDHP Tea Museum and tea processing factory.",
                "evening": "Campfire / quiet dinner at resort enjoying cool mountain air.",
                "notes": "Book Eravikulam tickets online to avoid long entry queues."
            },
            {
                "day_title": "Dams, Lakes & Echo Points",
                "morning": "Visit Mattupetty Dam; enjoy a speed boat ride across the tranquil lake.",
                "afternoon": "Stop at Echo Point and Kundala Lake; stroll through eucalyptus groves and rose gardens.",
                "evening": "Sunset views from Pothamedu View Point overlooking mist-covered valleys.",
                "notes": "Carry a light sweater; evening temperatures drop significantly."
            },
            {
                "day_title": "Spice Gardens & Departure",
                "morning": "Visit an organic spice plantation (cardamom, pepper, cinnamon, vanilla).",
                "afternoon": "Shop for genuine spices, homemade chocolates, and tea bags in Munnar market.",
                "evening": "Return drive to Kochi Airport for evening departure flight.",
                "notes": "Keep government photo IDs handy for domestic check-ins."
            }
        ]
    else:  # Generic fallback destination
        attraction_pool = [
            {
                "day_title": f"Arrival & Discovery in {destination}",
                "morning": f"Arrival and check-in to {hotel_name}. Unpack and settle in.",
                "afternoon": f"Walking orientation tour of central {destination} and historic downtown plaza.",
                "evening": "Local welcome dinner at a renowned traditional restaurant.",
                "notes": "Get local SIM or roaming configured; keep emergency contacts saved."
            },
            {
                "day_title": f"Top Landmarks & Heritage in {destination}",
                "morning": f"Visit the primary cultural museum or historical monument in {destination}.",
                "afternoon": "Art gallery, botanical gardens, and scenic public park stroll.",
                "evening": "Night market or cultural performance showcasing local traditions.",
                "notes": "Carry cash for small street vendors."
            },
            {
                "day_title": f"Local Neighborhoods & Hidden Gems",
                "morning": "Explore local artisan quarters, spice or craft markets.",
                "afternoon": "Scenic viewpoint or riverfront/coastal walkway.",
                "evening": "Leisurely dinner and cafe hopping.",
                "notes": "Ask hotel concierge for authentic off-the-beaten-path dining."
            },
            {
                "day_title": f"Souvenir Shopping & Departure",
                "morning": "Last-minute souvenir shopping and packing.",
                "afternoon": "Relaxing lunch and airport transfer.",
                "evening": "Check-in and flight departure.",
                "notes": "Ensure all duty-free receipts and boarding passes are prepared."
            }
        ]

    # Generate itinerary days
    itinerary_days = []
    for day_num in range(1, duration + 1):
        curr_date = base_date + timedelta(days=day_num - 1)
        template_idx = (day_num - 1) % len(attraction_pool)
        item = dict(attraction_pool[template_idx])
        
        # Modify notes if replanning occurred
        if replan_count > 0:
            item["notes"] += f" (Optimized for budget: self-guided exploration and free public transit)."

        # Weather integration into activity schedule
        if rain_expected and day_num in [1, 2]:
            item["afternoon"] = f"[Rain-adjusted indoor schedule]: {item['afternoon']}"

        itinerary_days.append({
            "day": day_num,
            "date": curr_date.strftime("%Y-%m-%d (%A)"),
            "title": item["day_title"],
            "morning": item["morning"],
            "afternoon": item["afternoon"],
            "evening": item["evening"],
            "notes": item["notes"]
        })

    return {
        **state,
        "itinerary": itinerary_days,
        "execution_steps": exec_steps
    }

# -------------------------------------------------------------
# 4. BUDGET AGENT (Pure Python Arithmetic - RULE 3 & 5)
# -------------------------------------------------------------
def budget_node(state: TripState) -> TripState:
    """
    Computes exact costs using pure Python arithmetic and MCP tool rates.
    Tests if total exceeds user budget.
    """
    exec_steps = list(state.get("execution_steps", []))
    exec_steps.append("Budget Agent: Calculating itemized costs (Flight + Hotel + Food + Transport + Activities)")

    duration = state.get("duration_days", 4)
    budget = state.get("budget", 80000.0)
    user_curr = state.get("currency", "INR")
    destination = state.get("destination", "Singapore")

    # 1. Flight Cost
    flight = state.get("selected_flight") or {}
    flight_price_raw = float(flight.get("price", 25000))
    flight_curr = flight.get("currency", "INR")
    flight_conv = mcp_tools.convert_currency(flight_price_raw, flight_curr, user_curr)
    flight_cost = flight_conv.get("converted_amount", flight_price_raw)

    # 2. Hotel Cost (price_per_night * duration)
    hotel = state.get("selected_hotel") or {}
    hotel_rate_raw = float(hotel.get("price_per_night", 7000))
    hotel_curr = hotel.get("currency", "INR")
    hotel_conv = mcp_tools.convert_currency(hotel_rate_raw, hotel_curr, user_curr)
    hotel_rate = hotel_conv.get("converted_amount", hotel_rate_raw)
    hotel_cost = round(hotel_rate * duration, 2)

    # 3. Daily Per-diem expenses (Food, Local Transport, Activities)
    daily_rates = _get_daily_rates(destination)
    
    # Check if replanned to reduce activity spend
    replan_count = state.get("replanning_count", 0)
    activity_multiplier = 0.6 if replan_count > 0 else 1.0

    food_cost = round(daily_rates["food"] * duration, 2)
    transport_cost = round(daily_rates["transport"] * duration, 2)
    activity_cost = round(daily_rates["activities"] * duration * activity_multiplier, 2)

    # 4. Total calculation (Rule 3: Pure Python Arithmetic)
    total_cost = round(flight_cost + hotel_cost + food_cost + transport_cost + activity_cost, 2)
    budget_exceeded = total_cost > budget

    exec_steps.append(
        f"Budget Check #{replan_count + 1}: Total {user_curr} {total_cost:,.2f} vs Budget {user_curr} {budget:,.2f} "
        f"({'EXCEEDED' if budget_exceeded else 'WITHIN BUDGET'})"
    )

    return {
        **state,
        "flight_cost": flight_cost,
        "hotel_cost": hotel_cost,
        "food_cost": food_cost,
        "transport_cost": transport_cost,
        "activity_cost": activity_cost,
        "total_cost": total_cost,
        "budget_exceeded": budget_exceeded,
        "execution_steps": exec_steps
    }

# -------------------------------------------------------------
# 5. REPLAN NODE (Conditional Cost Reduction)
# -------------------------------------------------------------
def replan_node(state: TripState) -> TripState:
    """
    Invoked when budget_exceeded is True and replanning_count < 2.
    Swaps hotel to cheaper tier, downgrades flight if needed,
    and scales back non-essential activity budgets.
    """
    exec_steps = list(state.get("execution_steps", []))
    replan_count = state.get("replanning_count", 0) + 1
    history = list(state.get("replanning_history", []))

    exec_steps.append(f"Re-planning Agent (Attempt {replan_count}/2): Finding lower-cost alternatives")

    prev_total = state.get("total_cost", 0.0)
    budget = state.get("budget", 0.0)
    user_curr = state.get("currency", "INR")
    
    current_hotel = state.get("selected_hotel") or {}
    current_flight = state.get("selected_flight") or {}
    hotels = state.get("hotels", [])
    flights = state.get("flights", [])

    actions = []

    # 1. Look for cheaper hotel
    current_hotel_price = current_hotel.get("price_per_night", 999999)
    cheaper_hotels = [h for h in hotels if h.get("price_per_night", 999999) < current_hotel_price]
    new_hotel = current_hotel
    if cheaper_hotels:
        # Pick lowest or next lower
        new_hotel = sorted(cheaper_hotels, key=lambda x: x.get("price_per_night", 0))[0]
        actions.append(
            f"Swapped hotel from '{current_hotel.get('hotel_name')}' ({user_curr} {current_hotel_price}/night) "
            f"to '{new_hotel.get('hotel_name')}' ({user_curr} {new_hotel.get('price_per_night')}/night)"
        )

    # 2. Look for cheaper flight
    current_flight_price = current_flight.get("price", 999999)
    cheaper_flights = [f for f in flights if f.get("price", 999999) < current_flight_price]
    new_flight = current_flight
    if cheaper_flights:
        new_flight = sorted(cheaper_flights, key=lambda x: x.get("price", 0))[0]
        actions.append(
            f"Swapped flight from '{current_flight.get('airline')}' ({user_curr} {current_flight_price}) "
            f"to '{new_flight.get('airline')}' ({user_curr} {new_flight.get('price')})"
        )

    # 3. Reduce paid attractions
    actions.append("Optimized activity expenses by prioritizing scenic public gardens, temples, and free cultural walking tours.")

    note = (
        f"Re-plan #{replan_count}: Estimated total ({user_curr} {prev_total:,.2f}) exceeded budget ({user_curr} {budget:,.2f}). "
        + " | ".join(actions)
    )
    history.append(note)

    return {
        **state,
        "selected_hotel": new_hotel,
        "selected_flight": new_flight,
        "replanning_count": replan_count,
        "replanning_history": history,
        "execution_steps": exec_steps
    }

# -------------------------------------------------------------
# 6. FINAL SUMMARY AGENT
# -------------------------------------------------------------
def final_summary_node(state: TripState) -> TripState:
    """
    Compiles the final user-facing response with full cost breakdown,
    flight/hotel selections, day-by-day itinerary, grounded visa info,
    weather outlook, events, sources, and guardrail disclaimers.
    """
    exec_steps = list(state.get("execution_steps", []))
    
    missing = state.get("missing_critical_info", [])
    if missing:
        exec_steps.append("Final Summary Agent: Halted due to missing critical information")
        missing_msg = "### Missing Information\n\nPlease provide the missing details to generate your plan:\n" + "\n".join([f"- {m}" for m in missing])
        return {
            **state,
            "final_response": missing_msg,
            "execution_steps": exec_steps
        }

    exec_steps.append("Final Summary Agent: Assembling comprehensive report and citations")

    destination = state.get("destination", "")
    duration = state.get("duration_days", 4)
    budget = state.get("budget", 0.0)
    user_curr = state.get("currency", "INR")
    total_cost = state.get("total_cost", 0.0)
    budget_exceeded = state.get("budget_exceeded", False)
    replan_count = state.get("replanning_count", 0)
    replan_history = state.get("replanning_history", [])

    flight = state.get("selected_flight") or {}
    hotel = state.get("selected_hotel") or {}
    weather_data = state.get("weather") or {}
    visa_info = state.get("visa_info", "")

    # Warnings collection
    warnings = list(state.get("warnings", []))
    warnings.append("PRICING DISCLAIMER: All flight and hotel rates shown are indicative demo quotes and do not represent live booking availability.")
    warnings.append("IMMIGRATION NOTICE: Visa rules, exemption programs, and border requirements can change at any time. Always consult the official embassy or immigration authority.")
    if weather_data.get("status") == "distant_future":
        warnings.append("WEATHER NOTICE: Live atmospheric forecasts are limited to 16 days. For distant travel dates, historical climate norms apply.")
    if budget_exceeded:
        warnings.append(f"BUDGET NOTICE: Total estimated expenses ({user_curr} {total_cost:,.2f}) exceed your stated budget of {user_curr} {budget:,.2f} despite {replan_count} re-planning attempts. Consider traveling in shoulder season or extending budget.")

    # Sources collection
    all_sources = []
    # RAG sources
    for rs in state.get("rag_sources", []):
        all_sources.append(rs)
    # Web search sources
    for ws in state.get("web_sources", []):
        all_sources.append(ws)
    # Weather source
    if weather_data.get("source"):
        all_sources.append({"title": "Open-Meteo Weather API", "url": "https://open-meteo.com", "type": "Weather Forecast Service"})
    # MCP / Data sources
    all_sources.append({"title": "Local Mock Flights Dataset", "url": "data/flights.json", "type": "Demo Inventory"})
    all_sources.append({"title": "Local Mock Hotels Dataset", "url": "data/hotels.json", "type": "Demo Inventory"})
    all_sources.append({"title": "Frankfurter Currency API", "url": "https://api.frankfurter.dev", "type": "Exchange Rates"})

    # Build formatted text response
    lines = []
    lines.append(f"# Trip Plan: {duration}-Day Journey to {destination} ✈️")
    lines.append(f"**Budget:** {user_curr} {budget:,.2f} | **Estimated Total:** {user_curr} {total_cost:,.2f} | **Status:** {'⚠️ Exceeded Budget' if budget_exceeded else '✅ Within Budget'}\n")

    if replan_history:
        lines.append("### ↻ Re-planning History")
        for h in replan_history:
            lines.append(f"- {h}")
        lines.append("")

    lines.append("### 💰 Budget & Cost Breakdown")
    lines.append(f"- **Flight ({flight.get('airline', 'N/A')}):** {user_curr} {state.get('flight_cost', 0):,.2f}")
    lines.append(f"- **Accommodation ({hotel.get('hotel_name', 'N/A')}, {duration} nights):** {user_curr} {state.get('hotel_cost', 0):,.2f}")
    lines.append(f"- **Food & Dining ({duration} days):** {user_curr} {state.get('food_cost', 0):,.2f}")
    lines.append(f"- **Local Transport (Metro/Cabs):** {user_curr} {state.get('transport_cost', 0):,.2f}")
    lines.append(f"- **Sightseeing & Activities:** {user_curr} {state.get('activity_cost', 0):,.2f}")
    lines.append(f"- **Grand Total:** **{user_curr} {total_cost:,.2f}**\n")

    lines.append("### ✈️ Selected Flight")
    lines.append(f"- **Airline:** {flight.get('airline', 'N/A')}")
    lines.append(f"- **Departure / Arrival:** {flight.get('departure', 'N/A')} ➔ {flight.get('arrival', 'N/A')}")
    lines.append(f"- **Indicative Price:** {flight.get('currency', user_curr)} {flight.get('price', 0):,.2f}\n")

    lines.append("### 🏨 Selected Accommodation")
    lines.append(f"- **Hotel:** {hotel.get('hotel_name', 'N/A')} ({hotel.get('category', 'Standard').capitalize()} Tier)")
    lines.append(f"- **Rating:** ⭐ {hotel.get('rating', '4.0')} / 5")
    lines.append(f"- **Rate:** {hotel.get('currency', user_curr)} {hotel.get('price_per_night', 0):,.2f} per night\n")

    lines.append("### 🌤️ Weather Outlook")
    lines.append(f"{weather_data.get('summary', 'Weather data not available.')}")
    if weather_data.get("recommendation"):
        lines.append(f"- *Recommendation:* {weather_data.get('recommendation')}\n")

    lines.append("### 🛂 Visa & Immigration Rules (RAG Grounded)")
    lines.append(visa_info or "No specific visa advisory document retrieved.")
    lines.append("")

    events = state.get("events", [])
    if events:
        lines.append("### 🎭 Local Events & Advisories")
        for ev in events:
            lines.append(f"- **{ev.get('title')}**: {ev.get('snippet')} [Read more]({ev.get('url')})")
        lines.append("")

    final_resp_str = "\n".join(lines)

    return {
        **state,
        "warnings": warnings,
        "final_response": final_resp_str,
        "execution_steps": exec_steps
    }
