

import streamlit as st
from datetime import date, timedelta
import pandas as pd
from graph import run_planner
import mcp_tools
import rag
import weather
from config import LLM_API_KEY, TAVILY_API_KEY


st.set_page_config(
    page_title="Smart Trip Planner ✈️",
    page_icon="✈️",
    layout="wide",
    initial_sidebar_state="expanded"
)


st.markdown("""
<style>
    .main-header {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-header {
        font-size: 1.1rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .badge-demo {
        background-color: #FEF3C7;
        color: #92400E;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-live {
        background-color: #D1FAE5;
        color: #065F46;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .exec-step {
        background-color: #F3F4F6;
        border-left: 4px solid #3B82F6;
        padding: 6px 12px;
        margin-bottom: 4px;
        border-radius: 0 4px 4px 0;
        font-family: monospace;
        font-size: 0.85rem;
    }
    .exec-replan {
        background-color: #FEF3C7;
        border-left: 4px solid #F59E0B;
        padding: 6px 12px;
        margin-bottom: 4px;
        border-radius: 0 4px 4px 0;
        font-family: monospace;
        font-size: 0.85rem;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.markdown('<div class="main-header">Smart Trip Planner ✈️</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-header">AI-powered, budget-aware travel planning with LangGraph, MCP tools, and Local RAG</div>', unsafe_allow_html=True)

default_start = date.today() + timedelta(days=20)
default_end = default_start + timedelta(days=3)

if "origin" not in st.session_state:
    st.session_state.origin = "Mumbai"
if "destination" not in st.session_state:
    st.session_state.destination = "Singapore"
if "start_date" not in st.session_state:
    st.session_state.start_date = default_start
if "end_date" not in st.session_state:
    st.session_state.end_date = default_end
if "budget" not in st.session_state:
    st.session_state.budget = 80000.0
if "currency" not in st.session_state:
    st.session_state.currency = "INR"
if "passport" not in st.session_state:
    st.session_state.passport = "India"
if "request_text" not in st.session_state:
    st.session_state.request_text = "Plan a 4-day trip to Singapore in December under Rs 80,000."
if "plan_result" not in st.session_state:
    st.session_state.plan_result = None


def load_scenario(name):
    if name == "singapore":
        st.session_state.origin = "Mumbai"
        st.session_state.destination = "Singapore"
        st.session_state.start_date = date.today() + timedelta(days=30)
        st.session_state.end_date = st.session_state.start_date + timedelta(days=3)
        st.session_state.budget = 80000.0
        st.session_state.currency = "INR"
        st.session_state.passport = "India"
        st.session_state.request_text = "Plan a 4-day trip to Singapore in December under Rs 80,000 with re-planning."
    elif name == "thailand_visa":
        st.session_state.origin = "Delhi"
        st.session_state.destination = "Bangkok"
        st.session_state.start_date = date.today() + timedelta(days=15)
        st.session_state.end_date = st.session_state.start_date + timedelta(days=3)
        st.session_state.budget = 65000.0
        st.session_state.currency = "INR"
        st.session_state.passport = "India"
        st.session_state.request_text = "Do I need a visa to visit Thailand on an Indian passport?"
    elif name == "munnar":
        st.session_state.origin = "Bengaluru"
        st.session_state.destination = "Munnar"
        st.session_state.start_date = date.today() + timedelta(days=4)
        st.session_state.end_date = st.session_state.start_date + timedelta(days=3)
        st.session_state.budget = 35000.0
        st.session_state.currency = "INR"
        st.session_state.passport = "India"
        st.session_state.request_text = "What's the weather like in Munnar next week? Plan scenic tea plantation tour."
    elif name == "cheaper_hotels":
        st.session_state.origin = "Mumbai"
        st.session_state.destination = "Singapore"
        st.session_state.start_date = date.today() + timedelta(days=20)
        st.session_state.end_date = st.session_state.start_date + timedelta(days=3)
        st.session_state.budget = 50000.0
        st.session_state.currency = "INR"
        st.session_state.passport = "India"
        st.session_state.request_text = "Suggest cheaper hotel options for my Singapore itinerary under tight budget."


with st.sidebar:
    st.subheader("Scenarios")
    col_sc1, col_sc2 = st.columns(2)
    with col_sc1:
        if st.button("Singapore Trip", use_container_width=True):
            load_scenario("singapore")
            st.rerun()
        if st.button("Munnar Weather", use_container_width=True):
            load_scenario("munnar")
            st.rerun()
    with col_sc2:
        if st.button("Thailand Visa", use_container_width=True):
            load_scenario("thailand_visa")
            st.rerun()
        if st.button("Cheaper Hotels", use_container_width=True):
            load_scenario("cheaper_hotels")
            st.rerun()

    st.divider()

    


with st.form("planner_form"):
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        origin_input = st.text_input("Starting Location (Origin)", value=st.session_state.origin)
    with col2:
        dest_input = st.text_input("Destination", value=st.session_state.destination)
    with col3:
        start_date_input = st.date_input("Start Date", value=st.session_state.start_date)
    with col4:
        end_date_input = st.date_input("End Date", value=st.session_state.end_date)

    col5, col6, col7 = st.columns(3)
    with col5:
        budget_input = st.number_input("Budget", value=float(st.session_state.budget), min_value=1000.0, step=5000.0)
    with col6:
        currency_input = st.selectbox("Currency", ["INR", "USD", "SGD", "EUR", "THB", "MYR"], index=0)
    with col7:
        passport_input = st.text_input("Passport Country", value=st.session_state.passport)

    request_input = st.text_input("Special Instructions / Free-text Query (Optional)", value=st.session_state.request_text)

    submit_button = st.form_submit_button("Plan My Trip", type="primary", use_container_width=True)

if submit_button:
 
    delta = (end_date_input - start_date_input).days + 1
    if delta <= 0:
        st.error("Error: End Date cannot be before Start Date.")
    else:
        with st.spinner("Executing LangGraph multi-agent workflow..."):
            result = run_planner(
                origin=origin_input,
                destination=dest_input,
                start_date=start_date_input.strftime("%Y-%m-%d"),
                end_date=end_date_input.strftime("%Y-%m-%d"),
                duration_days=delta,
                budget=budget_input,
                currency=currency_input,
                passport_country=passport_input,
                user_request=request_input
            )
            st.session_state.plan_result = result

res = st.session_state.plan_result

if res:
    st.divider()

  
    if res.get("missing_critical_info"):
        st.error("###  Missing Critical Constraints")
        for err in res["missing_critical_info"]:
            st.warning(f"• {err}")
    else:
       
        st.subheader(" Multi-Agent Execution Flow")
        steps = res.get("execution_steps", [])
        
        flow_col1, flow_col2 = st.columns([2, 1])
        with flow_col1:
            for s in steps:
                if "Re-planning" in s or "EXCEEDED" in s:
                    st.markdown(f"<div class='exec-replan'>↻ {s}</div>", unsafe_allow_html=True)
                else:
                    st.markdown(f"<div class='exec-step'>✓ {s}</div>", unsafe_allow_html=True)

        

        st.divider()

        
        st.subheader("1. Trip Overview & Budget Analysis")
        o_col1, o_col2, o_col3, o_col4 = st.columns(4)
        
        total_cost = res.get("total_cost", 0.0)
        budget = res.get("budget", 0.0)
        curr = res.get("currency", "INR")
        budget_exceeded = res.get("budget_exceeded", False)
        replan_count = res.get("replanning_count", 0)

        o_col1.metric("Destination", f"{res.get('destination')}")
        o_col2.metric("Duration", f"{res.get('duration_days')} Days")
        o_col3.metric("Stated Budget", f"{curr} {budget:,.2f}")
        o_col4.metric("Estimated Total", f"{curr} {total_cost:,.2f}", delta=f"{budget - total_cost:+,.2f} remaining", delta_color="normal" if not budget_exceeded else "inverse")

        if replan_count > 0:
            st.success(f"**Re-planning Triggered ({replan_count} attempt):** Initial plan exceeded your budget. The Planner agent automatically searched for lower-cost flights and hotels to fit your {curr} {budget:,.2f} limit.")
            with st.expander("View Re-planning Audit Log"):
                for entry in res.get("replanning_history", []):
                    st.markdown(f"- {entry}")

        if budget_exceeded:
            st.error(f"**Notice:** Total estimated cost exceeds your budget by {curr} {total_cost - budget:,.2f} even after {replan_count} re-planning cycles. Consider adjusting dates or hotel tiers.")

        cost_data = {
            "Expense Category": ["Flights (Return)", f"Hotel ({res.get('duration_days')} Nights)", "Food & Dining", "Local Transport", "Activities & Sightseeing"],
            f"Estimated Amount ({curr})": [
                res.get("flight_cost", 0),
                res.get("hotel_cost", 0),
                res.get("food_cost", 0),
                res.get("transport_cost", 0),
                res.get("activity_cost", 0)
            ],
            "Calculation Source": [
                "MCP search_flights (data/flights.json)",
                "MCP search_hotels (data/hotels.json)",
                "Daily destination per-diem logic",
                "Daily destination per-diem logic",
                "Attractions & walking trails logic"
            ]
        }
        st.table(pd.DataFrame(cost_data))

        tab_itin, tab_flight, tab_hotel, tab_weather, tab_visa, tab_events, tab_sources= st.tabs([
            " Day-by-Day Itinerary",
            " Flight Selection",
            " Hotel Selection",
            " Weather Outlook",
            " Visa Guidelines (RAG)",
            " Events & Advisories",
            " Sources & Citations"
        ])

        with tab_itin:
            st.subheader("Day-by-Day Schedule")
            itinerary = res.get("itinerary", [])
            for day_info in itinerary:
                with st.expander(f"Day {day_info.get('day')}: {day_info.get('title')} ({day_info.get('date')})", expanded=True):
                    st.markdown(f"**Morning:** {day_info.get('morning')}")
                    st.markdown(f"**Afternoon:** {day_info.get('afternoon')}")
                    st.markdown(f"**Evening:** {day_info.get('evening')}")
                    if day_info.get("notes"):
                        st.info(f" **Notes:** {day_info.get('notes')}")

        with tab_flight:
            st.subheader("Selected Flight (MCP Tool)")
            sf = res.get("selected_flight") or {}
            st.markdown(f"""
            - **Airline:** `{sf.get('airline', 'N/A')}`
            - **Route:** `{sf.get('origin', res.get('origin'))}` ➔ `{sf.get('destination', res.get('destination'))}`
            - **Timings:** Departure: `{sf.get('departure', 'N/A')}` | Arrival: `{sf.get('arrival', 'N/A')}`
            - **Price:** `{sf.get('currency', curr)} {sf.get('price', 0):,.2f}` <span class="badge-demo">Demo / Indicative Data</span>
            - **Data Source:** `{sf.get('source', 'MCP Flight Tool')}`
            """, unsafe_allow_html=True)
            
            with st.expander("View All Available Mock Flights for Route"):
                st.dataframe(pd.DataFrame(res.get("flights", [])))

        with tab_hotel:
            st.subheader("Selected Hotel (MCP Tool)")
            sh = res.get("selected_hotel") or {}
            st.markdown(f"""
            - **Hotel Name:** `{sh.get('hotel_name', 'N/A')}`
            - **Tier / Category:** `{sh.get('category', 'Standard').capitalize()}`
            - **Rating:**  `{sh.get('rating', '4.0')} / 5.0`
            - **Price per Night:** `{sh.get('currency', curr)} {sh.get('price_per_night', 0):,.2f}` <span class="badge-demo">Demo / Indicative Data</span>
            - **Amenities:** {', '.join(sh.get('amenities', []))}
            - **Data Source:** `{sh.get('source', 'MCP Hotel Tool')}`
            """, unsafe_allow_html=True)

            with st.expander("Compare with Alternative Hotels (Cheaper Options)"):
                st.dataframe(pd.DataFrame(res.get("hotels", [])))

        with tab_weather:
            st.subheader("Weather Forecast (Open-Meteo)")
            w_data = res.get("weather", {})
            st.markdown(f"**Status:** `{w_data.get('status', 'N/A')}`")
            st.markdown(f"**Summary:** {w_data.get('summary', 'No summary available.')}")
            if w_data.get("recommendation"):
                st.info(f"**Recommendation:** {w_data.get('recommendation')}")
            
            forecast_items = w_data.get("forecast", [])
            if forecast_items:
                st.dataframe(pd.DataFrame(forecast_items))
            st.caption(f"Source: {w_data.get('source', 'Open-Meteo')}")

        with tab_visa:
            st.subheader("Visa & Border Entry Rules (Local RAG)")
            st.markdown(res.get("visa_info", "No visa data retrieved."))
            
            st.warning(
                " **Official Verification Required:** Visa exemption policies and health requirements can change "
                "without notice. You must confirm with the destination embassy/consulate before traveling."
            )
            
            st.markdown("**Grounded RAG Sources:**")
            for rs in res.get("rag_sources", []):
                st.markdown(f"-  `{rs.get('title')}` (`{rs.get('url')}`)")

        with tab_events:
            st.subheader("Local Events, Festivals & Advisories (Tavily)")
            events = res.get("events", [])
            if events:
                for ev in events:
                    st.markdown(f"**{ev.get('title')}**")
                    st.markdown(f"{ev.get('snippet')}")
                    if ev.get("url"):
                        st.markdown(f"[Source Article / Link]({ev.get('url')})")
                    st.divider()
            else:
                st.info("Live web search is unavailable or no current events were returned. (Gracefully degraded without crashing).")

        with tab_sources:
            st.subheader("Complete Source Traceability")
            st.markdown("Every piece of external and retrieved information is attributed:")
            
            sources_list = []
            for rs in res.get("rag_sources", []):
                sources_list.append({"Component": "Visa / Policy", "Title / Resource": rs.get("title"), "URL / Path": rs.get("url"), "Type": "Local RAG"})
            for ws in res.get("web_sources", []):
                sources_list.append({"Component": "Events / Web", "Title / Resource": ws.get("title"), "URL / Path": ws.get("url"), "Type": "Tavily Search"})
            sources_list.append({"Component": "Weather", "Title / Resource": "Open-Meteo API", "URL / Path": "https://open-meteo.com", "Type": "Live API"})
            sources_list.append({"Component": "Flights", "Title / Resource": "Local Flights Mock", "URL / Path": "data/flights.json", "Type": "MCP Server"})
            sources_list.append({"Component": "Hotels", "Title / Resource": "Local Hotels Mock", "URL / Path": "data/hotels.json", "Type": "MCP Server"})
            sources_list.append({"Component": "Currency", "Title / Resource": "Frankfurter API / Fallback", "URL / Path": "https://api.frankfurter.dev", "Type": "MCP Tool"})
            
            st.dataframe(pd.DataFrame(sources_list), use_container_width=True)

       
           
