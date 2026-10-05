import requests
from config import FALLBACK_EXCHANGE_RATES_TO_INR

def convert_currency(amount: float, from_currency: str, to_currency: str) -> dict:
    """
    Converts currency using Frankfurter API with graceful fallback to predefined demo rates.
    Returns:
        dict: {
            "converted_amount": float,
            "rate": float,
            "from_currency": str,
            "to_currency": str,
            "source": str,
            "is_fallback": bool
        }
    """
    amount = float(amount)
    from_curr = from_currency.upper().strip()
    to_curr = to_currency.upper().strip()

    if from_curr == to_curr:
        return {
            "converted_amount": round(amount, 2),
            "rate": 1.0,
            "from_currency": from_curr,
            "to_currency": to_curr,
            "source": "Identical currency (1:1)",
            "is_fallback": False
        }

    # Attempt Frankfurter API
    # Note: Frankfurter supports EUR, USD, GBP, SGD, THB, MYR, etc. (base and symbols)
    for api_url in ["https://api.frankfurter.dev/v1/latest", "https://api.frankfurter.app/latest"]:
        try:
            params = {"amount": amount, "from": from_curr, "to": to_curr}
            response = requests.get(api_url, params=params, timeout=3)
            if response.status_code == 200:
                data = response.json()
                if "rates" in data and to_curr in data["rates"]:
                    converted = float(data["rates"][to_curr])
                    rate = round(converted / amount, 4) if amount != 0 else 0
                    return {
                        "converted_amount": round(converted, 2),
                        "rate": rate,
                        "from_currency": from_curr,
                        "to_currency": to_curr,
                        "source": f"Frankfurter API ({api_url})",
                        "is_fallback": False
                    }
        except Exception:
            continue

    # Fallback to predefined demo rates
    # Relative to INR
    from_rate_inr = FALLBACK_EXCHANGE_RATES_TO_INR.get(from_curr, 1.0)
    to_rate_inr = FALLBACK_EXCHANGE_RATES_TO_INR.get(to_curr, 1.0)

    # amount in INR = amount * from_rate_inr
    # amount in target = (amount in INR) / to_rate_inr
    effective_rate = from_rate_inr / to_rate_inr
    converted = amount * effective_rate

    return {
        "converted_amount": round(converted, 2),
        "rate": round(effective_rate, 4),
        "from_currency": from_curr,
        "to_currency": to_curr,
        "source": "Predefined Demo Exchange Rates (Frankfurter API unavailable or currency not listed)",
        "is_fallback": True
    }
