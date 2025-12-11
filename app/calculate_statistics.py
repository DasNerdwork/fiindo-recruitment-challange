from sqlalchemy.orm import Session
from datetime import datetime, timezone
import json
from app.database import SessionLocal
from src.models import RawFinancialData, RawGeneralData, TickerStatistics


# -------------------- Financial helper functions --------------------

def calculate_pe_ratio(price, eps):
    """
    P/E Ratio = Price per Share / Earnings per Share (EPS).  
    Used to evaluate how expensive a stock is relative to its earnings.
    """
    if price is None or eps is None or eps == 0:
        return None
    return price / eps


def calculate_revenue_growth(rev_q1, rev_q2):
    """
    Revenue Growth = (CurrentQuarter - PreviousQuarter) / PreviousQuarter.  
    rev_q1 = previous quarter  
    rev_q2 = current quarter
    """
    if rev_q1 is None or rev_q2 is None or rev_q1 == 0:
        return None
    return (rev_q2 - rev_q1) / rev_q1


def calculate_net_income_ttm(last_quarters, fy_net_income=None):
    """
    TTM = Trailing Twelve Months net income.  
    Sum of the last 4 quarterly net-income values.  
    Falls back to fiscal-year (FY) value if quarterly data is incomplete.
    """
    filtered = [x for x in last_quarters if x is not None]

    if len(filtered) >= 4:
        return sum(filtered)
    
    # Less than 4 quarters -> try to fall back to FY
    if fy_net_income is not None:
        return fy_net_income

    return None


def calculate_debt_ratio(debt, equity):
    """
    Debt Ratio = Total Debt / Total Equity.  
    High values indicate high leverage and potentially high risk.
    """
    if equity is None or equity <= 0:
        return None
    return debt / equity

# -------------------- Main processing function --------------------

def run(db: Session):
    print("Loading joined RawFinancialData + RawGeneralData rows...")

    financial_rows = (
        db.query(RawFinancialData, RawGeneralData)
        .join(RawGeneralData, RawGeneralData.symbol == RawFinancialData.symbol)
        .all()
    )

    print(f"Loaded {len(financial_rows)} rows.")

    if not financial_rows:
        print("No financial rows found. Abort.")
        return

    # -------------------- Process each symbol --------------------

    for fin, gen in financial_rows:
        print(f"\n--- Processing symbol: {fin.symbol} ---")
        print(f"Industry: {gen.industry}")

        #  Parse income statement (typically quarterly data)
        try:
            income = fin.income_data
            if isinstance(income, str):  # if stored as JSON string in DB
                income = json.loads(income)

            if not income:
                print(f"WARNING: income_data missing for {fin.symbol}")
                continue

            # Sort newest first
            income = sorted(
                income, key=lambda x: x.get("date", "1970-01-01"), reverse=True
            )
            print(f"Income entries: {len(income)}")

        except Exception as e:
            print(f"ERROR: Invalid income_data for {fin.symbol}: {e}")
            continue

        # Parse balance sheet (typically yearly data)
        try:
            balance = fin.balance_data
            if isinstance(balance, str):
                balance = json.loads(balance)

            if not balance:
                print(f"WARNING: balance_data missing for {fin.symbol}")
                balance = []

            balance = sorted(
                balance, key=lambda x: x.get("date", "1970-01-01"), reverse=True
            )

            print(f"Balance entries: {len(balance)}")

            # FY = Full Fiscal Year aggregated values
            last_fy = next((b for b in balance if b.get("period") == "FY"), None)

        except Exception as e:
            print(f"ERROR: Invalid balance_data for {fin.symbol}: {e}")
            balance = []
            last_fy = None

        # Parse general data (e.g., current stock price)
        price = None
        try:
            gd = gen.general_data
            if isinstance(gd, str):
                gd = json.loads(gd)

            price = gd.get("fundamentals", {}).get("profile", {}).get("data", [{}])[0].get("price")

            if price is None:
                print(f"WARNING: Price not found for {fin.symbol}")
            print(f"Price: {price}")

        except Exception as e:
            print(f"ERROR reading general_data for {fin.symbol}: {e}")


        # -------------------- Begin metric calculations --------------------

        # --- EPS last quarter ---
        eps_last_quarter = next(
            (q.get("eps") for q in income if q.get("period", "").startswith("Q")),
            None
        )
        if eps_last_quarter is None:
            print(f"WARNING: EPS last quarter missing for {fin.symbol}")

        # --- PE Ratio ---
        pe_ratio = calculate_pe_ratio(price, eps_last_quarter)
        if pe_ratio is None:
            print(
                f"WARNING: Cannot calculate PE Ratio for {fin.symbol} (price={price}, eps={eps_last_quarter})"
            )
        print(f"PE Ratio: {pe_ratio}")

        # --- Revenue Growth (QoQ) ---
        quarters = [q for q in income if q.get("period", "").startswith("Q")]
        print(f"Quarter count: {len(quarters)}")

        revenue_growth = None
        if len(quarters) >= 2:
            rev_q1 = quarters[1].get("revenue")  # previous quarter
            rev_q2 = quarters[0].get("revenue")  # current quarter
            revenue_growth = calculate_revenue_growth(rev_q1, rev_q2)
            print(f"Revenue Q-1: {rev_q1}, Revenue Q0: {rev_q2}")

        if revenue_growth is None:
            print(f"WARNING: Revenue growth cannot be calculated for {fin.symbol}")
        print(f"Revenue Growth: {revenue_growth}")

        # --- Net Income TTM ---
        last_four_net_income = [q.get("netIncome") for q in quarters[:4]]
        net_income_ttm = calculate_net_income_ttm(
            last_four_net_income,
            fy_net_income=last_fy.get("netIncome") if last_fy else None
        )

        if net_income_ttm is None:
            print(
                f"WARNING: Net income TTM missing or insufficient for {fin.symbol} "
                f"(last_four_net_income={last_four_net_income})"
            )
        print(f"Net income TTM: {net_income_ttm}")

        # --- Debt Ratio (based on FY data) ---
        debt_ratio = None
        if last_fy:
            debt_ratio = calculate_debt_ratio(
                last_fy.get("totalDebt"),
                last_fy.get("totalEquity")
            )

            if debt_ratio is None:
                print(
                    f"WARNING: Cannot calculate debt ratio for {fin.symbol} "
                    f"(totalDebt={last_fy.get('totalDebt')}, totalEquity={last_fy.get('totalEquity')})"
                )
        else:
            print("No FY balance found.")

        print(f"Debt Ratio: {debt_ratio}")

        # --- Skip if nothing was calculated ---
        if all(v is None for v in [pe_ratio, revenue_growth, net_income_ttm, debt_ratio]):
            print(f"WARNING: No valid statistics for {fin.symbol}. Skipping DB update.")
            continue

        # -------------------- Upsert into TickerStatistics table --------------------

        existing = db.get(TickerStatistics, fin.symbol)
        if existing:
            print("Updating existing ticker_statistics entry.")
        else:
            print("Creating new ticker_statistics entry.")
            existing = TickerStatistics(symbol=fin.symbol)

        existing.pe_ratio = pe_ratio
        existing.revenue_growth = revenue_growth
        existing.net_income_ttm = net_income_ttm
        existing.debt_ratio = debt_ratio
        existing.industry = gen.industry
        existing.calculated_at = datetime.now(timezone.utc)

        db.merge(existing)

    db.commit()
    print("\nFinished calculating ticker statistics.")

# -------------------- MAIN --------------------
if __name__ == "__main__":
    print("Starting calculate_statistics.py...")
    db = SessionLocal()
    try:
        run(db)
    finally:
        db.close()