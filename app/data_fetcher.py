import asyncio
import aiohttp
from aiolimiter import AsyncLimiter
import requests
import time
import argparse
import json
import os

API_BASE = "https://api.test.fiindo.com/api/v1"
AUTH_HEADER = {"Authorization": "Bearer florian.falk"}
CACHE_FILE = "cached_symbols.json"
TARGET_INDUSTRIES = {
    "Banks - Diversified",
    "Software - Application",
    "Consumer Electronics",
}

rate_limiter = AsyncLimiter(4, 1)  # limit to 4 requests per second (one less than specified)
MAX_RETRIES = 5 # limit retries to avoid infinite loops
BASE_DELAY = 1 # base exponental delay of 1 second 

def fetch_symbols():
    r = requests.get(f"{API_BASE}/symbols", headers=AUTH_HEADER)
    r.raise_for_status()
    return r.json()["symbols"]

def load_cached_symbols():
    if os.path.exists(CACHE_FILE):
        with open(CACHE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_cached_symbols(symbols):
    with open(CACHE_FILE, "w") as f:
        json.dump(list(symbols), f)

def filter_target_symbols(symbols, target_industries_set, general_data_map):
    """Gibt nur Symbole zurück, die in den Zielindustrien sind"""
    filtered = set()
    for symbol in symbols:
        general = general_data_map.get(symbol)
        if not general:
            continue
        industry = extract_industry(general)
        if industry in target_industries_set:
            filtered.add(symbol)
    return filtered

async def fetch_general(session, symbol):
    url = f"{API_BASE}/general/{symbol}"
    delay = BASE_DELAY

    for attempt in range(MAX_RETRIES):
        async with rate_limiter:
            try:
                async with session.get(url, headers=AUTH_HEADER) as resp:
                    if resp.status == 429:
                        print(f"{symbol}: 429 Too Many Requests, attempt {attempt + 1}")
                        await asyncio.sleep(delay)
                        delay *= 2 # exponential delay
                        continue

                    resp.raise_for_status()
                    return await resp.json()
            except aiohttp.ClientError as e:
                print(f"{symbol}: Request failed: {e}, attempt {attempt + 1}")
                await asyncio.sleep(delay)
                delay *= 2

    print(f"{symbol}: FAILED after {MAX_RETRIES} retries")
    return None


def extract_industry(general):
    return (
        general.get("fundamentals", {})
               .get("profile", {})
               .get("data", [{}])[0]
               .get("industry")
    )


async def collect_industry_stats(symbols, limit=100):
    stats = {k: 0 for k in TARGET_INDUSTRIES}
    stats["_missing_or_other"] = 0

    async with aiohttp.ClientSession() as session:
        tasks = [fetch_general(session, s) for s in symbols[:limit]]
        results = await asyncio.gather(*tasks)

        for symbol, general in zip(symbols[:limit], results):
            if general is None:
                stats["_missing_or_other"] += 1
                continue

            industry = extract_industry(general)
            print(f"{symbol}: industry={industry!r}")

            if industry in TARGET_INDUSTRIES:
                stats[industry] += 1
            else:
                stats["_missing_or_other"] += 1

    return stats


# Startup
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--cached", action="store_true", help="Use cached symbols only")
    args = parser.parse_args()

    start_time = time.perf_counter()

    symbols = fetch_symbols()
    print(f"Total symbols: {len(symbols)}")

    cached_symbols = load_cached_symbols()
    print(f"Cached symbols: {len(cached_symbols)}")

    # If --cached is set only use symbols from the cache file
    if args.cached and cached_symbols:
        symbols_to_process = list(cached_symbols)
    else:
        symbols_to_process = symbols

    general_data_map = {}

    async def collect_and_cache(symbols):
        stats = {k: 0 for k in TARGET_INDUSTRIES}
        stats["_missing_or_other"] = 0

        async with aiohttp.ClientSession() as session:
            tasks = [fetch_general(session, s) for s in symbols]
            results = await asyncio.gather(*tasks)

            for symbol, general in zip(symbols, results):
                general_data_map[symbol] = general
                if general is None:
                    stats["_missing_or_other"] += 1
                    continue

                industry = extract_industry(general)
                print(f"{symbol}: industry={industry!r}")

                if industry in TARGET_INDUSTRIES:
                    stats[industry] += 1
                else:
                    stats["_missing_or_other"] += 1

        return stats

    stats = asyncio.run(collect_and_cache(symbols_to_process))

    # If --cached is not set save symbols from target industries to cache
    if not args.cached:
        target_symbols = filter_target_symbols(symbols, TARGET_INDUSTRIES, general_data_map)
        save_cached_symbols(target_symbols)
        print(f"Saved {len(target_symbols)} symbols to cache")

    print("\nIndustry Distribution:")
    for k, v in stats.items():
        print(f"{k}: {v}")

    end_time = time.perf_counter()
    print(f"\nScript finished in {end_time - start_time:.2f} seconds")