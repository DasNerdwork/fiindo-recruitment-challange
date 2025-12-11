# Fiindo ETL - Coding Challenge

[Jump to the Quickstart Part](#quickstart-step-by-step)

### Quick summary of repository layout

- `app/` - ETL scripts:

    - `speedboost.py` - enables the API speedboost for given bearer
    - `fetch_general.py` - fetches the general information of symbols
    - `fetch_financials.py` - fetches the financial statements used for calcs later
    - `calculate_statistics.py` - calculates the per ticker statistics
    - `aggregate_industries.py` - aggregates the industry data
- `run_all.py` - sequential runner calling each step
- `utils.py` - generic fetch + rate-limit helpers
- `src/models.py` - SQLAlchemy model definitions
- `alembic/` - Alembic migration environment and versions
- `requirements.txt`, `Dockerfile`, `docker-compose.yml`, `.env` - Necessary configs

## Prerequisites
- Python 3.11+
- Docker & docker-compose (if you want containerized runs)
- SQLite (used by SQLAlchemy in this project)

Python libs are listed in requirements.txt:
```python
SQLAlchemy>=2.0.0
alembic>=1.12.0
requests>=2.32.0
aiohttp>=3.9.0
aiolimiter>=1.1.0
pandas>=2.0.0
python-dotenv>=1.0.0
```
To install inside the Docker container:

```bash
docker-compose run --rm fiindo-etl pip install -r requirements.txt
```

## Environment variables

Create a `.env` in `/app` folder with content:
```bash
API_BASE=https://api.test.fiindo.com/api/v1
API_KEY=firstname.lastname
```
All scripts read `API_BASE` and `API_KEY` via python-dotenv. `AUTH_HEADER` is built as:
```python
AUTH_HEADER = {"Authorization": f"Bearer {API_KEY}"}
```

## Database (Alembic + SQLite)

DB file: `fiindo_challenge.db`. Models are in `src/models.py`.

#### Typical workflows

Create / migrate DB (use alembic from project root):

```bash
# apply all migrations:
alembic upgrade head
```
Reset DB when you dropped tables or removed the file:
```bash
rm fiindo_challenge.db
alembic stamp base
alembic upgrade head    # apply all migrations fresh
```

## Running the pipeline
### Single-step scripts

You can run each module individually (works in the container and locally):
```bash
python -m app.speedboost
python -m app.fetch_general       # has optional --cached flag to speed up reruns
python -m app.fetch_financials
python -m app.calculate_statistics
python -m app.aggregate_industries
```

`fetch_general` supports `--cached` to read only symbols already stored in raw_general_data which speeds reruns.

### Run all steps sequentially

`run_all.py` already runs the exact sequence. Locally:

```bash
docker-compose run --rm fiindo-etl python run_all.py
```

If you prefer container commands for each step:
```bash
docker-compose run --rm fiindo-etl python -m app.fetch_general --cached
```

## Rate-limiting and speed boost

- `app/utils.py` provides `fetch(session, url, rate_limiter)` with retries and exponential backoff (default 4 requests/sec).
- Financial endpoints seem to use a higher limit therefore it is adjusted in the `fetch_financials` code (configurable).
- To temporarily request higher API throughput run the speedboost script:

```bash
docker-compose run --rm fiindo-etl python -m app.speedboost
```

This calls `/speedboost` with your bearer identity; use it before heavy runs if you have the right token.

---

### Notes about data & calculations

- Raw responses are stored in:
    - `raw_general_data.general_data (JSON)`
    - `raw_financial_data.income_data / balance_data (JSON)`

- Per-ticker statistics are calculated and stored in `ticker_statistics`.
    - PE ratio uses last quarter EPS and latest price from general_data.
    - Revenue growth is quarter-over-quarter (latest two quarters).
    - Net income TTM uses last 4 quarters or falls back to latest FY `netIncome` if quarters are missing.
    - Debt ratio uses last FY (`totalDebt / totalEquity`) if equity > 0.

- Industry aggregation computes average PE, average revenue growth (mean over available tickers), and sum of revenue (prefers last quarter revenue, falls back 
to FY revenue).

Scripts are defensive: if numeric inputs are missing or invalid, the code will skip calculations and avoid writing misleading zeros.

## Quickstart step-by-step

1. Clone the repository
```bash
git clone <your-repo-url> fiindo-recruitment-challenge
cd fiindo-recruitment-challenge
```

2. Create .env in `app/` folder
```bash
# file: app/.env
API_BASE=https://api.test.fiindo.com/api/v1
API_KEY=firstname.lastname
```

3. Build docker container image
```bash
docker-compose build --no-cache
# or simple build
docker-compose build
```

4. Prepare the database with Alembic

```bash
# apply migrations
alembic upgrade head
```

5. Verify DB tables (optional)
```bash
sqlite3 fiindo_challenge.db
# then in sqlite prompt:
.schema
.tables
.quit
```

6. Run the ETL pipeline inside Docker

```bash
# run the full runner inside the fiindo-etl service
docker-compose run --rm fiindo-etl python run_all.py

# or run single steps
docker-compose run --rm fiindo-etl python -m app.fetch_general --cached
docker-compose run --rm fiindo-etl python -m app.fetch_financials
```

### Re-runs & development tips

Use `python -m app.fetch_general --cached` to only fetch symbols already present in `raw_general_data` (faster iteration).

To rebuild dependencies after changing requirements.txt:
```bash
# inside docker flow:
docker-compose run --rm fiindo-etl pip install -r requirements.txt
# or rebuild image:
docker-compose build
```

If you want a single migration instead of many (destructive local-only step)

```bash
# remove or move alembic/versions/*
# then generate a fresh migration from models:
alembic revision --autogenerate -m "initial schema"
alembic upgrade head
```
> Warning: deleting migrations is destructive for shared repositories; only do this for local testing.