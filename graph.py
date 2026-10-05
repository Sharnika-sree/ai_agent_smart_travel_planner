"""
LangGraph Workflow Orchestration for Smart Trip Planner.
Implements the multi-agent graph:
  START -> Planner -> Weather -> Itinerary -> Budget -> (Conditional Replan) -> Final Summary -> END
"""

from langgraph.graph import StateGraph, START, END
from state import TripState
from agents import (
    planner_node,
    weather_node,
    itinerary_node,
    budget_node,
    replan_node,
    final_summary_node
)

def should_replan(state: TripState) -> str:
    """
    Conditional routing edge from Budget node.
    - If critical information is missing, proceed immediately to summary/error.
    - If budget is exceeded and replanning_count < 2, route to replan.
    - Otherwise, proceed to final summary.
    """
    if state.get("missing_critical_info"):
        return "final_summary"
    
    if state.get("budget_exceeded", False) and state.get("replanning_count", 0) < 2:
        return "replan"
    
    return "final_summary"

def build_trip_planner_graph():
    """
    Constructs and compiles the LangGraph StateGraph.
    """
    workflow = StateGraph(TripState)

    # Register Nodes
    workflow.add_node("planner", planner_node)
    workflow.add_node("weather", weather_node)
    workflow.add_node("itinerary", itinerary_node)
    workflow.add_node("budget", budget_node)
    workflow.add_node("replan", replan_node)
    workflow.add_node("final_summary", final_summary_node)

    # Define Linear Edges
    workflow.add_edge(START, "planner")
    workflow.add_edge("planner", "weather")
    workflow.add_edge("weather", "itinerary")
    workflow.add_edge("itinerary", "budget")

    # Define Conditional Edge for Budget & Replanning
    workflow.add_conditional_edges(
        "budget",
        should_replan,
        {
            "replan": "replan",
            "final_summary": "final_summary"
        }
    )

    # Edge from Replan back to Itinerary -> Budget
    workflow.add_edge("replan", "itinerary")

    # Final edge to END
    workflow.add_edge("final_summary", END)

    return workflow.compile()

# Global compiled graph
planner_graph = build_trip_planner_graph()

def run_planner(
    origin: str,
    destination: str,
    start_date: str = "",
    end_date: str = "",
    duration_days: int = 4,
    budget: float = 80000.0,
    currency: str = "INR",
    passport_country: str = "India",
    user_request: str = ""
) -> TripState:
    """
    High-level entry point to execute the LangGraph workflow.
    """
    initial_state: TripState = {
        "user_request": user_request,
        "origin": origin,
        "destination": destination,
        "start_date": start_date,
        "end_date": end_date,
        "duration_days": duration_days,
        "budget": float(budget),
        "currency": currency.upper(),
        "passport_country": passport_country,
        "execution_steps": [],
        "replanning_count": 0,
        "replanning_history": [],
        "warnings": []
    }
    
    final_output = planner_graph.invoke(initial_state)
    return final_output
