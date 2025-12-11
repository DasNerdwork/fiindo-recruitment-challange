import asyncio
import aiohttp
import json
from datetime import datetime, timezone
from aiolimiter import AsyncLimiter
from app.database import SessionLocal
from src.models import RawGeneralData
from .utils import fetch, fetch_symbols, API_BASE

# -------------------- CONFIG --------------------
TARGET_INDUSTRIES = {
    "Banks - Diversified",
    "Software - Application",
    "Consumer Electronics",
}

# Use lower rate limit for general info because we get too many 429s otherwise
general_rate_limiter = AsyncLimiter(4, 1)  # 4 req/sec

# -------------------- UTILITY --------------------
def extract_industry(general):
    """Extract industry from general JSON."""
    return (
        general.get("fundamentals", {})
               .get("profile", {})
               .get("data", [{}])[0]
               .get("industry")
    )

# -------------------- ASYNC FETCH --------------------
async def fetch_general(session, symbol):
    """Fetch general data for a single symbol."""
    url = f"{API_BASE}/general/{symbol}"
    return await fetch(session, url, rate_limiter=general_rate_limiter)

async def fetch_and_save(symbols):
    """Fetch general data for multiple symbols and save to DB."""
    stats = {k: 0 for k in TARGET_INDUSTRIES}
    stats["_missing_or_other"] = 0

    db = SessionLocal()
    async with aiohttp.ClientSession() as session:
        tasks = [fetch_general(session, s) for s in symbols]
        results = await asyncio.gather(*tasks)

        for symbol, general in zip(symbols, results):
            if general is None:
                stats["_missing_or_other"] += 1
                continue

            industry = extract_industry(general)
            if industry in TARGET_INDUSTRIES:
                stats[industry] += 1
                db.merge(RawGeneralData(
                    symbol=symbol,
                    industry=industry,
                    general_data=json.dumps(general),
                    fetched_at=datetime.now(timezone.utc)
                ))
            else:
                stats["_missing_or_other"] += 1

    db.commit()
    db.close()
    return stats

# -------------------- MAIN --------------------
if __name__ == "__main__":
    import argparse, time
    parser = argparse.ArgumentParser()
    parser.add_argument("--cached", action="store_true")
    args = parser.parse_args()

    start = time.perf_counter()
    db = SessionLocal()
    symbols = [row.symbol for row in db.query(RawGeneralData.symbol).all()] if args.cached else fetch_symbols()
    db.close()

    print(f"Processing {len(symbols)} symbols...")
    stats = asyncio.run(fetch_and_save(symbols))
    for k, v in stats.items():
        print(f"{k}: {v}")
    print(f"Finished in {time.perf_counter() - start:.2f}s")
