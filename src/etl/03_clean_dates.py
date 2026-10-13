from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
PROCESSED = ROOT / "data/processed"
REPORTS = ROOT / "data/reports/date_quality"

PROCESSED.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# 1. Load data
# --------------------------------------------------

dates = pd.read_excel(SOURCE, sheet_name="DateTable")
orders = pd.read_csv(
    PROCESSED / "orders_clean.csv",
    parse_dates=["order_date_clean"]
)

raw_dates = dates.copy(deep=True)

dates["date_clean"] = pd.to_datetime(
    dates["Date"], errors="coerce"
).dt.normalize()

# --------------------------------------------------
# 2. Validate calendar attributes
# --------------------------------------------------

dates["year_expected"] = dates["date_clean"].dt.year
dates["month_expected"] = dates["date_clean"].dt.month
dates["month_name_expected"] = dates["date_clean"].dt.month_name()
dates["quarter_expected"] = (
    "Q" + dates["date_clean"].dt.quarter.astype("string")
)
dates["day_expected"] = dates["date_clean"].dt.day

def normalized(series):
    return series.astype("string").str.strip().str.casefold()

checks = {
    "Invalid Dates": int(dates["date_clean"].isna().sum()),
    "Duplicate Dates": int(dates["date_clean"].duplicated().sum()),
    "Year Mismatches": int(
        (
            pd.to_numeric(dates["Year"], errors="coerce")
            != dates["year_expected"]
        ).fillna(True).sum()
    ),
    "Month Number Mismatches": int(
        (
            pd.to_numeric(dates["MonthNo"], errors="coerce")
            != dates["month_expected"]
        ).fillna(True).sum()
    ),
    "Month Name Mismatches": int(
        (
            normalized(dates["MonthName"])
            != normalized(dates["month_name_expected"])
        ).fillna(True).sum()
    ),
    "Quarter Mismatches": int(
        (
            normalized(dates["Quarter"])
            != normalized(dates["quarter_expected"])
        ).fillna(True).sum()
    ),
    "Day Mismatches": int(
        (
            pd.to_numeric(dates["Day"], errors="coerce")
            != dates["day_expected"]
        ).fillna(True).sum()
    ),
}

# --------------------------------------------------
# 3. Date coverage
# --------------------------------------------------

order_dates = orders["order_date_clean"].dt.normalize()

date_set = set(dates["date_clean"].dropna())

unmatched_orders = orders.loc[
    ~order_dates.isin(date_set)
].copy()

# Check gaps within DateTable's own range
calendar_range = pd.date_range(
    dates["date_clean"].min(),
    dates["date_clean"].max(),
    freq="D"
)

missing_calendar_dates = calendar_range.difference(
    pd.DatetimeIndex(dates["date_clean"].dropna())
)

# --------------------------------------------------
# 4. Create reliable derived attributes
# --------------------------------------------------

dates["year_clean"] = dates["date_clean"].dt.year
dates["month_no_clean"] = dates["date_clean"].dt.month
dates["month_name_clean"] = dates["date_clean"].dt.month_name()
dates["quarter_clean"] = (
    "Q" + dates["date_clean"].dt.quarter.astype("string")
)
dates["day_of_month_clean"] = dates["date_clean"].dt.day
dates["day_of_week_clean"] = dates["date_clean"].dt.day_name()
dates["is_weekend"] = (
    dates["date_clean"].dt.dayofweek >= 5
)

# --------------------------------------------------
# 5. Summary
# --------------------------------------------------

summary_rows = [
    ["Total Calendar Rows", len(dates)],
    ["Calendar Start", str(dates["date_clean"].min().date())],
    ["Calendar End", str(dates["date_clean"].max().date())],
    ["Order Start", str(order_dates.min().date())],
    ["Order End", str(order_dates.max().date())],
    ["Orders Outside Calendar", len(unmatched_orders)],
    ["Missing Dates Within Calendar Range",
     len(missing_calendar_dates)],
]

summary_rows.extend(checks.items())

summary = pd.DataFrame(
    summary_rows,
    columns=["Metric", "Value"]
)

# --------------------------------------------------
# 6. Validate raw preservation and counts
# --------------------------------------------------

assert len(dates) == 1000
assert len(orders) == 200000

for col in raw_dates.columns:
    assert dates[col].equals(raw_dates[col])

assert len(unmatched_orders) == 0

assert (
    len(dates["date_clean"].dropna())
    + checks["Invalid Dates"]
    == len(dates)
)

# --------------------------------------------------
# 7. Export
# --------------------------------------------------

dates.to_csv(
    PROCESSED / "dates_clean.csv",
    index=False,
    encoding="utf-8-sig"
)

summary.to_csv(
    REPORTS / "date_quality_summary.csv",
    index=False,
    encoding="utf-8-sig"
)

unmatched_orders.to_csv(
    REPORTS / "orders_outside_calendar.csv",
    index=False,
    encoding="utf-8-sig"
)

pd.DataFrame({
    "MissingDate": missing_calendar_dates
}).to_csv(
    REPORTS / "calendar_gaps.csv",
    index=False,
    encoding="utf-8-sig"
)

print("=" * 65)
print("FOODPULSE 360 | DATE QUALITY & TIME INTELLIGENCE")
print("=" * 65)

print(summary.to_string(index=False))

print("\n[PASS] Raw DateTable columns preserved.")
print("[PASS] All orders covered by calendar.")
print("[SUCCESS] 4 output files generated.")