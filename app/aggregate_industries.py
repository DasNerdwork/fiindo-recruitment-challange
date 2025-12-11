import json
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from app.database import SessionLocal
from src.models import RawFinancialData, RawGeneralData, TickerStatistics, IndustryStatistics

def run(db: Session):
    print("Running industry aggregation...")

    # Join TickerStatistics -> RawGeneralData, to get industry info
    stats = (
        db.query(TickerStatistics, RawGeneralData)
        .join(RawGeneralData, RawGeneralData.symbol == TickerStatistics.symbol)
        .all()
    )

    if not stats:
        print("No ticker statistics found. Abort.")
        return

    industries = {}

    # Group ticker-level metrics by industry
    for ts, gen in stats:
        industry = gen.industry
        print(f"Processing ticker statistic: {ts.symbol} (industry={industry})")

        if industry not in industries:
            industries[industry] = {
                "pe": [],
                "growth": [],
                "symbols": []
            }

        # Only include non-null values into aggregation lists
        if ts.pe_ratio is not None:
            industries[industry]["pe"].append(ts.pe_ratio)
        else:
            print(f"  PE ratio missing for {ts.symbol}")

        if ts.revenue_growth is not None:
            industries[industry]["growth"].append(ts.revenue_growth)
        else:
            print(f"  Revenue growth missing for {ts.symbol}")

        industries[industry]["symbols"].append(ts.symbol)

    # --- Per-industry aggregation ---
    for ind, d in industries.items():
        print(f"\n--- Aggregating industry: {ind} ---")
        print(f"Symbols: {d['symbols']}")

        tickers = d["symbols"]
        revenues = []

        for t in tickers:
            fin = db.get(RawFinancialData, t)
            if not fin or not fin.income_data:
                print(f"  No financial data or income_data for {t}")
                continue

            income = fin.income_data
            if isinstance(income, str):
                try:
                    income = json.loads(income)
                except Exception as e:
                    print(f"  Failed to decode JSON for {t}: {e}")
                    continue

            if not isinstance(income, list) or not income:
                print(f"  income_data invalid or empty for {t}")
                continue

            # Sort by date descending to pick latest entries
            income_sorted = sorted(income, key=lambda x: x.get("date", "1970-01-01"), reverse=True)

            # Prefer last quarter revenue, fallback to full year
            last_quarter = next((q for q in income_sorted if q.get("period", "").startswith("Q")), None)
            revenue_value = None
            if last_quarter and last_quarter.get("revenue") is not None:
                revenue_value = last_quarter.get("revenue")
                print(f"  Using Q revenue: {revenue_value}")
            else:
                fy = next((q for q in income_sorted if q.get("period") == "FY"), None)
                if fy and fy.get("revenue") is not None:
                    revenue_value = fy.get("revenue")
                    print(f"  Using FY revenue: {revenue_value}")
                else:
                    print(f"  No revenue data available for {t}")

            if revenue_value is not None:
                revenues.append(revenue_value)

        # Calculate industry-level aggregates
        avg_pe = sum(d["pe"]) / len(d["pe"]) if d["pe"] else None
        avg_growth = sum(d["growth"]) / len(d["growth"]) if d["growth"] else None
        sum_revenue = sum(revenues) if revenues else None

        print(f"\nCalculated values for industry {ind}:")
        print(f"  avg_pe_ratio = {avg_pe}")
        print(f"  avg_revenue_growth = {avg_growth}")
        print(f"  sum_revenue = {sum_revenue}")

        # Upsert in DB
        existing = db.get(IndustryStatistics, ind)
        if not existing:
            print(f"  Creating new IndustryStatistics for {ind}")
            existing = IndustryStatistics(industry=ind)
        else:
            print(f"  Updating existing IndustryStatistics for {ind}")

        existing.avg_pe_ratio = avg_pe
        existing.avg_revenue_growth = avg_growth
        existing.sum_revenue = sum_revenue
        existing.calculated_at = datetime.now(timezone.utc)

        db.merge(existing)

    db.commit()
    print("\nFinished industry aggregation.")


# -------------------- MAIN --------------------
if __name__ == "__main__":
    print("Starting aggregate_industries.py...")
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()
