import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
KNOWLEDGE_DIR = BASE_DIR / "knowledge"

# API Keys
LLM_API_KEY = os.getenv("LLM_API_KEY") or os.getenv("OPENAI_API_KEY") or ""
TAVILY_API_KEY = os.getenv("TAVILY_API_KEY") or ""
LLM_MODEL = os.getenv("LLM_MODEL", "gpt-4o-mini")
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "openai")  # openai, gemini, or demo

# Predefined Fallback Exchange Rates (relative to INR)
FALLBACK_EXCHANGE_RATES_TO_INR = {
    "INR": 1.0,
    "USD": 83.50,
    "SGD": 63.50,
    "THB": 2.45,
    "MYR": 19.50,
    "EUR": 91.00,
    "GBP": 107.00
}

# Standard daily per-diem approximations in INR by destination tier
ESTIMATED_DAILY_EXPENSES = {
    "singapore": {"food": 2500, "transport": 1000, "activities": 3000},
    "bangkok": {"food": 1200, "transport": 600, "activities": 1500},
    "thailand": {"food": 1200, "transport": 600, "activities": 1500},
    "kuala lumpur": {"food": 1400, "transport": 700, "activities": 1800},
    "malaysia": {"food": 1400, "transport": 700, "activities": 1800},
    "munnar": {"food": 800, "transport": 500, "activities": 800},
    "default": {"food": 1500, "transport": 800, "activities": 1500}
}
