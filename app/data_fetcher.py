import requests
import json

API_BASE = "https://api.test.fiindo.com/api/v1"
AUTH_HEADER = {"Authorization": "Bearer Florian.Falk"}
STATEMENTS = ["income_statement", "balance_sheet_statement", "cash_flow_statement"]

def fetch_symbols():
    response = requests.get(f"{API_BASE}/symbols", headers=AUTH_HEADER)
    response.raise_for_status()
    return response.json()["symbols"]

def fetch_general(symbol):
    response = requests.get(f"{API_BASE}/general/{symbol}", headers=AUTH_HEADER)
    response.raise_for_status()
    return response.json()

def fetch_financials(symbol, statement="income_statement"):
    if statement not in STATEMENTS:
        raise ValueError(f"Invalid statement: {statement}. Expected one of {STATEMENTS}")
    response = requests.get(f"{API_BASE}/financials/{symbol}/{statement}", headers=AUTH_HEADER)
    response.raise_for_status()
    return response.json()

if __name__ == "__main__":
    symbols = fetch_symbols()
    print(f"Count of found symbols: {len(symbols)}")

    
    for symbol in symbols[:1]:  # first single symbol for testing
        try:
            general = fetch_general(symbol)
            financials_data = fetch_financials(symbol)

            # Save general info
            with open(f"{symbol}_general.json", "w", encoding="utf-8") as f:
                json.dump(general, f, ensure_ascii=False, indent=2)

            # Save financials
            with open(f"{symbol}_financials.json", "w", encoding="utf-8") as f:
                json.dump(financials_data, f, ensure_ascii=False, indent=2)

            print(f"{symbol} -> JSONs saved.")

        except requests.HTTPError as e:
            print(f"Error on {symbol}: {e}")