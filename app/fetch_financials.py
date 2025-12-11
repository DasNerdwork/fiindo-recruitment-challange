import asyncio
import aiohttp
from datetime import datetime, timezone
from aiolimiter import AsyncLimiter
from app.database import SessionLocal
from src.models import RawFinancialData, RawGeneralData
from .utils import fetch, API_BASE

financial_rate_limiter = AsyncLimiter(5, 1) # 5 requests / second (using speedboost?)

async def fetch_financials(session, symbol):
    """Fetch income and balance sheet for a symbol."""
    results = {}
    statements = ["income_statement", "balance_sheet_statement"]

    for stmt in statements:
        url = f"{API_BASE}/financials/{symbol}/{stmt}"
        raw = await fetch(session, url, rate_limiter=financial_rate_limiter)
        if not raw:
            results[stmt] = None
            continue

        if stmt == "income_statement":
            # Extract last 8 income statement records with relevant fields
            results["income_data"] = [
                {
                    "date": row["date"],
                    "period": row["period"],
                    "revenue": row.get("revenue"),
                    "netIncome": row.get("netIncome"),
                    "eps": row.get("eps")
                }
                for row in raw.get("fundamentals", {}).get("financials", {}).get("income_statement", {}).get("data", [])
            ][:8]
        elif stmt == "balance_sheet_statement":
            # Extract last 2 balance sheet records
            results["balance_data"] = [
                {
                    "date": row["date"],
                    "period": row["period"],
                    "totalDebt": row.get("totalDebt"),
                    "totalEquity": row.get("totalStockholdersEquity")
                }
                for row in raw.get("fundamentals", {}).get("financials", {}).get("balance_sheet_statement", {}).get("data", [])
            ][:2]

    # Skip invalid entries
    if not results.get("income_data") and not results.get("balance_data"):
        return None

    results["symbol"] = symbol
    return results

async def fetch_and_save(symbols):
    """
    Concurrently fetch financial data for all given symbols and store them
    into the database using upsert behavior.
    """
    db = SessionLocal()
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_financials(session, s) for s in symbols]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for i, data in enumerate(results, 1):
            if isinstance(data, Exception) or not data:
                print(f"[{i}/{len(symbols)}] Failed or no data")
                continue

            db.merge(RawFinancialData(
                symbol=data["symbol"],
                income_data=data.get("income_data"),
                balance_data=data.get("balance_data"),
                fetched_at=datetime.now(timezone.utc)
            ))
            db.commit()

    db.close()
    print("Finished saving all financial data.")

# -------------------- MAIN --------------------
def main():
    db = SessionLocal()
    symbols = [row.symbol for row in db.query(RawGeneralData.symbol).all()]
    db.close()

    print(f"Processing {len(symbols)} symbols...")
    asyncio.run(fetch_and_save(symbols))

if __name__ == "__main__":
    main()
