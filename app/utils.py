import asyncio
import aiohttp
from aiolimiter import AsyncLimiter
import requests
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# API configuration
API_BASE = os.getenv("API_BASE")  # e.g., "https://api.test.fiindo.com/api/v1"
API_KEY = os.getenv("API_KEY")    # e.g., "firstname.lastname"
AUTH_HEADER = {"Authorization": f"Bearer {API_KEY}"}

# Default global rate limiter
default_rate_limiter = AsyncLimiter(4, 1)  # 4 requests/sec
MAX_RETRIES = 5
BASE_DELAY = 1


def fetch_symbols():
    """Fetch all symbols from the API."""
    r = requests.get(f"{API_BASE}/symbols", headers=AUTH_HEADER)
    r.raise_for_status()
    return r.json()["symbols"]


def load_cached_symbols_from_db(session, model):
    """Load symbols already stored in the DB."""
    return [row.symbol for row in session.query(model.symbol).all()]


async def fetch(session: aiohttp.ClientSession, url: str, rate_limiter: AsyncLimiter = None):
    """
    Generic async fetch function with retries and exponential backoff.
    - `url`: full API URL
    - `rate_limiter`: AsyncLimiter instance (different per endpoint if needed)
    """
    delay = BASE_DELAY
    limiter = rate_limiter or default_rate_limiter

    for attempt in range(MAX_RETRIES):
        async with limiter:
            try:
                async with session.get(url, headers=AUTH_HEADER) as resp:
                    if resp.status == 429:
                        await asyncio.sleep(delay)
                        delay *= 2
                        continue
                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientError:
                await asyncio.sleep(delay)
                delay *= 2

    return None