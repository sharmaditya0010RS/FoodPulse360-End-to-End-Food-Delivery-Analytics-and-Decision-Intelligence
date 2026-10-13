from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/reports/restaurant_quality"
OUTPUT.mkdir(parents=True, exist_ok=True)

restaurants = pd.read_excel(SOURCE, sheet_name="Restaurants")
orders = pd.read_excel(
    SOURCE,
    sheet_name="Orders",
    usecols=["RestaurantID", "OrderID"]
)

total = len(restaurants)

def missing(series):
    return (
        series.isna()
        | series.astype("string").str.strip().eq("").fillna(False)
    )

# --------------------------------------------------
# 1. Column completeness
# --------------------------------------------------

completeness = pd.DataFrame([
    {
        "Column": col,
        "Missing": int(missing(restaurants[col]).sum()),
        "MissingPct": round(
            missing(restaurants[col]).mean() * 100, 2
        ),
        "UniqueValues": restaurants[col].nunique(dropna=True)
    }
    for col in restaurants.columns
]).sort_values("Missing", ascending=False)

# --------------------------------------------------
# 2. Rating validation
# --------------------------------------------------

rating_raw = (
    restaurants["rate"]
    .astype("string")
    .str.strip()
)

rating_numeric = pd.to_numeric(
    rating_raw.str.extract(r"^(\d+(?:\.\d+)?)")[0],
    errors="coerce"
)

rating_missing = missing(restaurants["rate"])

rating_checks = {
    "Total Restaurants": total,
    "Missing Ratings": int(rating_missing.sum()),
    "Non-Numeric Rating Labels": int(
        (~rating_missing & rating_numeric.isna()).sum()
    ),
    "Ratings Below 0": int((rating_numeric < 0).sum()),
    "Ratings Above 5": int((rating_numeric > 5).sum()),
    "Valid Numeric Ratings": int(
        rating_numeric.between(0, 5).sum()
    ),
}

# --------------------------------------------------
# 3. Votes and cost validation
# --------------------------------------------------

votes = pd.to_numeric(
    restaurants["votes"], errors="coerce"
)

cost = pd.to_numeric(
    restaurants["approx_cost(for two people)"]
    .astype("string")
    .str.replace(",", "", regex=False)
    .str.strip(),
    errors="coerce"
)

quality_checks = {
    **rating_checks,
    "Missing Votes": int(votes.isna().sum()),
    "Negative Votes": int((votes < 0).sum()),
    "Missing/Unparseable Cost": int(cost.isna().sum()),
    "Zero Cost": int((cost == 0).sum()),
    "Negative Cost": int((cost < 0).sum()),
}

quality = pd.DataFrame(
    quality_checks.items(),
    columns=["Metric", "Value"]
)

# --------------------------------------------------
# 4. Restaurant coverage in orders
# --------------------------------------------------

ordered_restaurants = set(
    orders["RestaurantID"].dropna()
)

restaurants["HasOrders"] = (
    restaurants["RestaurantID"].isin(ordered_restaurants)
)

coverage = pd.DataFrame([
    ["Total Restaurants", total],
    ["Restaurants With Orders", int(restaurants["HasOrders"].sum())],
    ["Restaurants Without Orders", int((~restaurants["HasOrders"]).sum())],
    ["Restaurant Coverage Pct",
     round(restaurants["HasOrders"].mean() * 100, 2)],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 5. Top categorical distributions
# --------------------------------------------------

categories = []

for col in [
    "online_order",
    "book_table",
    "location",
    "rest_type",
    "listed_in(type)",
    "listed_in(city)"
]:
    counts = (
        restaurants[col]
        .fillna("<MISSING>")
        .astype(str)
        .value_counts()
        .head(20)
    )

    for value, count in counts.items():
        categories.append({
            "Column": col,
            "Category": value,
            "Count": int(count),
            "Pct": round(count / total * 100, 2)
        })

category_report = pd.DataFrame(categories)

# --------------------------------------------------
# 6. Validation
# --------------------------------------------------

assert len(restaurants) == 56250
assert restaurants["RestaurantID"].is_unique

assert (
    int(restaurants["HasOrders"].sum())
    + int((~restaurants["HasOrders"]).sum())
    == total
)

assert int(completeness["Missing"].sum()) == 46599

# --------------------------------------------------
# 7. Save reports
# --------------------------------------------------

reports = {
    "column_completeness.csv": completeness,
    "restaurant_quality_checks.csv": quality,
    "restaurant_order_coverage.csv": coverage,
    "restaurant_categories.csv": category_report,
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 60)
print("FOODPULSE 360 | RESTAURANT QUALITY AUDIT")
print("=" * 60)

print("\nCOLUMN COMPLETENESS")
print(completeness.to_string(index=False))

print("\nQUALITY CHECKS")
print(quality.to_string(index=False))

print("\nORDER COVERAGE")
print(coverage.to_string(index=False))

print("\n[PASS] Restaurant counts reconciled.")
print("[PASS] Missing cells reconciled: 46,599.")
print("[SUCCESS] 4 reports saved.")