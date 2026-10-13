from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/processed"
REPORTS = ROOT / "data/reports/cleaning"

OUTPUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

# --------------------------------------------------
# 1. Load raw tables
# --------------------------------------------------

customers = pd.read_excel(SOURCE, sheet_name="Customers")
orders = pd.read_excel(SOURCE, sheet_name="Orders")

raw_customers = customers.copy(deep=True)
raw_orders = orders.copy(deep=True)

# --------------------------------------------------
# 2. Customer cleaning
# --------------------------------------------------

customers["signup_date_clean"] = pd.to_datetime(
    customers["SignupDate"], errors="coerce"
).dt.normalize()

for col in ["CustomerName", "City", "CustomerType"]:
    customers[col + "_clean"] = (
        customers[col].astype("string").str.strip()
    )

    customers.loc[
        customers[col + "_clean"].eq("").fillna(False),
        col + "_clean"
    ] = pd.NA

customers["customer_quality_issue"] = (
    customers["signup_date_clean"].isna()
    | customers[
        ["CustomerName_clean", "City_clean", "CustomerType_clean"]
    ].isna().any(axis=1)
)

# --------------------------------------------------
# 3. Order cleaning
# --------------------------------------------------

orders["order_date_clean"] = pd.to_datetime(
    orders["OrderDate"], errors="coerce"
).dt.normalize()

orders["order_value_clean"] = pd.to_numeric(
    orders["OrderValue"], errors="coerce"
)

orders["delivery_mins_clean"] = pd.to_numeric(
    orders["DeliveryTimeMins"], errors="coerce"
)

orders["quantity_clean"] = pd.to_numeric(
    orders["Quantity"], errors="coerce"
)

orders["order_status_clean"] = (
    orders["OrderStatus"].astype("string").str.strip()
)

valid_statuses = {"Delivered", "Delayed", "Cancelled"}

orders["order_quality_issue"] = (
    orders["order_date_clean"].isna()
    | orders["order_value_clean"].isna()
    | orders["order_value_clean"].le(0)
    | orders["delivery_mins_clean"].isna()
    | orders["delivery_mins_clean"].le(0)
    | orders["quantity_clean"].isna()
    | orders["quantity_clean"].le(0)
    | ~orders["order_status_clean"].isin(valid_statuses)
).fillna(True)

# --------------------------------------------------
# 4. Chronology validation
# --------------------------------------------------

signup_lookup = customers[
    ["CustomerID", "signup_date_clean"]
]

orders = orders.merge(
    signup_lookup,
    on="CustomerID",
    how="left",
    validate="many_to_one"
)

orders["days_before_signup"] = (
    orders["signup_date_clean"] - orders["order_date_clean"]
).dt.days

orders["order_before_signup"] = (
    orders["days_before_signup"] > 0
).fillna(False)

# --------------------------------------------------
# 5. Business metric eligibility flags
# --------------------------------------------------

orders["is_delivered"] = (
    orders["order_status_clean"] == "Delivered"
).fillna(False)

orders["is_delayed"] = (
    orders["order_status_clean"] == "Delayed"
).fillna(False)

orders["is_cancelled"] = (
    orders["order_status_clean"] == "Cancelled"
).fillna(False)

# Conservative completed-order value
orders["delivered_order_value"] = (
    orders["order_value_clean"]
    .where(orders["is_delivered"], 0)
)

# Alternative scenario, not confirmed revenue
orders["delivered_plus_delayed_value"] = (
    orders["order_value_clean"]
    .where(
        orders["is_delivered"] | orders["is_delayed"],
        0
    )
)

# Signup-based analyses must exclude chronology anomalies
orders["signup_cohort_eligible"] = (
    ~orders["order_before_signup"]
    & ~orders["order_quality_issue"]
    & orders["signup_date_clean"].notna()
).fillna(False)

# --------------------------------------------------
# 6. Validate raw preservation
# --------------------------------------------------

assert len(customers) == 20000
assert len(orders) == 200000

assert customers["CustomerID"].is_unique
assert orders["OrderID"].is_unique

for col in raw_customers.columns:
    assert customers[col].equals(raw_customers[col])

for col in raw_orders.columns:
    assert orders[col].equals(raw_orders[col])

# --------------------------------------------------
# 7. Independent KPI reconciliation
# --------------------------------------------------

assert int(orders["order_before_signup"].sum()) == 18372

assert int(orders["is_delivered"].sum()) == 160227
assert int(orders["is_delayed"].sum()) == 19826
assert int(orders["is_cancelled"].sum()) == 19947

assert orders["order_value_clean"].sum() == 164914494

assert orders["delivered_order_value"].sum() == 132092968

assert (
    orders["delivered_plus_delayed_value"].sum()
    == 148471541
)

assert int(orders["order_quality_issue"].sum()) == 0

# --------------------------------------------------
# 8. Summary
# --------------------------------------------------

summary = pd.DataFrame([
    ["Total Customers", len(customers)],
    ["Customer Quality Issues",
     int(customers["customer_quality_issue"].sum())],
    ["Total Orders", len(orders)],
    ["Order Quality Issues",
     int(orders["order_quality_issue"].sum())],
    ["Orders Before Signup",
     int(orders["order_before_signup"].sum())],
    ["Signup Cohort Eligible Orders",
     int(orders["signup_cohort_eligible"].sum())],
    ["Delivered Orders", int(orders["is_delivered"].sum())],
    ["Delayed Orders", int(orders["is_delayed"].sum())],
    ["Cancelled Orders", int(orders["is_cancelled"].sum())],
    ["Recorded Order Value", orders["order_value_clean"].sum()],
    ["Delivered Order Value",
     orders["delivered_order_value"].sum()],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 9. Export
# --------------------------------------------------

customers.to_csv(
    OUTPUT / "customers_clean.csv",
    index=False,
    encoding="utf-8-sig"
)

orders.to_csv(
    OUTPUT / "orders_clean.csv",
    index=False,
    encoding="utf-8-sig"
)

summary.to_csv(
    REPORTS / "customer_order_cleaning_summary.csv",
    index=False,
    encoding="utf-8-sig"
)

print("=" * 65)
print("FOODPULSE 360 | CUSTOMER & ORDER CLEANING")
print("=" * 65)

print(summary.to_string(index=False))

print("\n[PASS] Raw columns preserved.")
print("[PASS] Customer and order counts preserved.")
print("[PASS] Chronology flags reconciled.")
print("[PASS] Financial KPIs reconciled.")
print("[SUCCESS] 3 output files generated.")