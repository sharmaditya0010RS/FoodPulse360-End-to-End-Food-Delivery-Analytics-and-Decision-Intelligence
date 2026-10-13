from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data/processed"
REPORTS = ROOT / "data/reports/etl"
REPORTS.mkdir(parents=True, exist_ok=True)

# 1. Load cleaned datasets
orders = pd.read_csv(PROCESSED / "orders_clean.csv")
customers = pd.read_csv(PROCESSED / "customers_clean.csv")
restaurants = pd.read_csv(PROCESSED / "restaurants_clean.csv")
dates = pd.read_csv(PROCESSED / "dates_clean.csv")

# 2. Select only needed dimension fields
customer_dim = customers[
    ["CustomerID", "City_clean", "CustomerType_clean",
     "signup_date_clean"]
].rename(columns={
    "City_clean": "customer_city",
    "CustomerType_clean": "customer_type",
    "signup_date_clean": "customer_signup_date"
})

restaurant_dim = restaurants[
    ["RestaurantID", "name_clean", "location_clean",
     "rest_type_clean", "cuisines_clean",
     "rating_clean", "votes_clean", "cost_for_two_clean",
     "suspected_contamination"]
].rename(columns={
    "name_clean": "restaurant_name",
    "location_clean": "restaurant_location",
    "rest_type_clean": "restaurant_type",
    "cuisines_clean": "restaurant_cuisines",
    "rating_clean": "restaurant_rating",
    "votes_clean": "restaurant_votes",
    "cost_for_two_clean": "restaurant_cost_for_two",
    "suspected_contamination": "restaurant_quality_flag"
})

date_dim = dates[
    ["date_clean", "year_clean", "month_no_clean",
     "month_name_clean", "quarter_clean",
     "day_of_week_clean", "is_weekend"]
].rename(columns={
    "date_clean": "order_date_clean",
    "year_clean": "order_year",
    "month_no_clean": "order_month",
    "month_name_clean": "order_month_name",
    "quarter_clean": "order_quarter",
    "day_of_week_clean": "order_day_name"
})

# 3. Safe many-to-one joins
mart = orders.merge(
    customer_dim,
    on="CustomerID",
    how="left",
    validate="many_to_one"
)

mart = mart.merge(
    restaurant_dim,
    on="RestaurantID",
    how="left",
    validate="many_to_one"
)

mart = mart.merge(
    date_dim,
    on="order_date_clean",
    how="left",
    validate="many_to_one"
)

# 4. Eligibility flags
mart["restaurant_analysis_eligible"] = (
    ~mart["restaurant_quality_flag"].fillna(True).astype(bool)
)

mart["customer_cohort_eligible"] = (
    mart["signup_cohort_eligible"].fillna(False).astype(bool)
)

# 5. Financial metric aliases
mart["recorded_order_value"] = mart["order_value_clean"]
mart["confirmed_delivered_value"] = mart["delivered_order_value"]

# 6. Independent checks
assert len(mart) == 200000
assert mart["OrderID"].is_unique
assert mart["customer_city"].notna().all()
assert mart["restaurant_name"].notna().sum() > 0
assert mart["order_year"].notna().all()

assert mart["recorded_order_value"].sum() == 164914494
assert mart["confirmed_delivered_value"].sum() == 132092968
assert mart["order_before_signup"].sum() == 18372
assert mart["restaurant_analysis_eligible"].sum() == 184141

# 7. Summary
summary = pd.DataFrame([
    ["Total Analytics Rows", len(mart)],
    ["Unique Orders", mart["OrderID"].nunique()],
    ["Unique Customers", mart["CustomerID"].nunique()],
    ["Unique Restaurants", mart["RestaurantID"].nunique()],
    ["Restaurant Analysis Eligible Orders",
     int(mart["restaurant_analysis_eligible"].sum())],
    ["Customer Cohort Eligible Orders",
     int(mart["customer_cohort_eligible"].sum())],
    ["Recorded Order Value",
     mart["recorded_order_value"].sum()],
    ["Confirmed Delivered Value",
     mart["confirmed_delivered_value"].sum()],
], columns=["Metric", "Value"])

# 8. Export
mart.to_csv(
    PROCESSED / "orders_analytics_mart.csv",
    index=False,
    encoding="utf-8-sig"
)

summary.to_csv(
    REPORTS / "analytics_mart_summary.csv",
    index=False,
    encoding="utf-8-sig"
)

print("=" * 65)
print("FOODPULSE 360 | ANALYTICS MART BUILD")
print("=" * 65)
print(summary.to_string(index=False))

print("\n[PASS] Join cardinality preserved.")
print("[PASS] Order and revenue metrics reconciled.")
print("[PASS] Quality eligibility flags applied.")
print("[SUCCESS] Analytics mart generated.")