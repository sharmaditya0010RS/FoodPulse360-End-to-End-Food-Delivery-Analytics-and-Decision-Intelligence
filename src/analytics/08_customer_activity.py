from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"
OUTPUT = ROOT / "data/reports/customer_activity"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    SOURCE,
    parse_dates=["order_date_clean"]
)

df["recorded_order_value"] = pd.to_numeric(
    df["recorded_order_value"],
    errors="raise"
)

assert len(df) == 200000
assert df["OrderID"].is_unique

observation_end = df["order_date_clean"].max()
observation_start = df["order_date_clean"].min()

# --------------------------------------------------
# 1. Customer-level last observed activity
# --------------------------------------------------

customers = (
    df.groupby("CustomerID")
    .agg(
        FirstOrder=("order_date_clean", "min"),
        LastOrder=("order_date_clean", "max"),
        Orders=("OrderID", "count"),
        RecordedValue=("recorded_order_value", "sum")
    )
    .reset_index()
)

customers["DaysSinceLastOrder"] = (
    observation_end - customers["LastOrder"]
).dt.days

customers["ActivityStatus"] = np.select(
    [
        customers["DaysSinceLastOrder"] <= 30,
        customers["DaysSinceLastOrder"] <= 90,
        customers["DaysSinceLastOrder"] <= 180
    ],
    [
        "Active 0-30 Days",
        "Inactive 31-90 Days",
        "Inactive 91-180 Days"
    ],
    default="Inactive 181+ Days"
)

# These are descriptive inactivity bands,
# not proven churn labels.

status = (
    customers.groupby("ActivityStatus")
    .agg(
        Customers=("CustomerID", "count"),
        HistoricalOrders=("Orders", "sum"),
        HistoricalRecordedValue=("RecordedValue", "sum"),
        MedianDaysSinceLastOrder=(
            "DaysSinceLastOrder", "median"
        )
    )
    .reset_index()
)

status["CustomerSharePct"] = (
    status["Customers"] / len(customers) * 100
)

# --------------------------------------------------
# 2. Monthly active customers
# --------------------------------------------------

df["ActivityMonth"] = (
    df["order_date_clean"].dt.to_period("M")
)

monthly = (
    df.groupby("ActivityMonth")
    .agg(
        Orders=("OrderID", "count"),
        ActiveCustomers=("CustomerID", "nunique"),
        RecordedValue=("recorded_order_value", "sum")
    )
    .reset_index()
    .sort_values("ActivityMonth")
)

monthly["OrdersPerActiveCustomer"] = (
    monthly["Orders"] / monthly["ActiveCustomers"]
)

# --------------------------------------------------
# 3. Reactivation after 90+ days of inactivity
# --------------------------------------------------

# Use distinct customer-order dates, so multiple
# orders on the same day do not create fake gaps.

activity_dates = (
    df[["CustomerID", "order_date_clean"]]
    .drop_duplicates()
    .sort_values(["CustomerID", "order_date_clean"])
    .copy()
)

activity_dates["PreviousActiveDate"] = (
    activity_dates.groupby("CustomerID")[
        "order_date_clean"
    ].shift()
)

activity_dates["GapDays"] = (
    activity_dates["order_date_clean"]
    - activity_dates["PreviousActiveDate"]
).dt.days

# 90+ elapsed days between observed active dates.
activity_dates["ReactivatedAfter90Days"] = (
    activity_dates["GapDays"] >= 90
)

reactivation_events = activity_dates.loc[
    activity_dates["ReactivatedAfter90Days"]
].copy()

reactivation_events["ReactivationMonth"] = (
    reactivation_events["order_date_clean"]
    .dt.to_period("M")
)

reactivation_monthly = (
    reactivation_events.groupby("ReactivationMonth")
    .agg(
        ReactivationEvents=("CustomerID", "count"),
        ReactivatedCustomers=("CustomerID", "nunique"),
        MedianGapDays=("GapDays", "median")
    )
    .reset_index()
)

# --------------------------------------------------
# 4. Monthly new-to-observation vs returning
# --------------------------------------------------

first_month = (
    customers[["CustomerID", "FirstOrder"]]
    .assign(
        FirstObservedMonth=lambda x:
        x["FirstOrder"].dt.to_period("M")
    )
    [["CustomerID", "FirstObservedMonth"]]
)

customer_month = (
    df[["CustomerID", "ActivityMonth"]]
    .drop_duplicates()
    .merge(
        first_month,
        on="CustomerID",
        validate="many_to_one"
    )
)

customer_month["FirstObservedThisMonth"] = (
    customer_month["ActivityMonth"]
    == customer_month["FirstObservedMonth"]
)

monthly_customer_mix = (
    customer_month.groupby("ActivityMonth")
    .agg(
        ActiveCustomers=("CustomerID", "count"),
        FirstObservedCustomers=(
            "FirstObservedThisMonth", "sum"
        )
    )
    .reset_index()
)

monthly_customer_mix["PreviouslyObservedCustomers"] = (
    monthly_customer_mix["ActiveCustomers"]
    - monthly_customer_mix["FirstObservedCustomers"]
)

# --------------------------------------------------
# 5. Reconciliation
# --------------------------------------------------

assert len(customers) == 20000
assert customers["Orders"].sum() == 200000
assert customers["RecordedValue"].sum() == 164914494

assert status["Customers"].sum() == 20000
assert monthly["Orders"].sum() == 200000

assert (
    monthly_customer_mix["FirstObservedCustomers"].sum()
    == 20000
)

assert (
    monthly_customer_mix["ActiveCustomers"].sum()
    == len(customer_month)
)

assert (
    reactivation_events["GapDays"] >= 90
).all()

assert (
    activity_dates["GapDays"].dropna() >= 1
).all()

# --------------------------------------------------
# 6. Summary
# --------------------------------------------------

summary = pd.DataFrame([
    ["Total Customers", len(customers)],
    ["Total Orders", len(df)],
    ["Observation Start", str(observation_start.date())],
    ["Observation End", str(observation_end.date())],
    ["Distinct Customer Active Dates", len(activity_dates)],
    ["Reactivation Events (90+ Day Gap)",
     len(reactivation_events)],
    ["Unique Reactivated Customers",
     reactivation_events["CustomerID"].nunique()],
    ["Median Days Since Last Order",
     customers["DaysSinceLastOrder"].median()]
], columns=["Metric", "Value"])

# --------------------------------------------------
# 7. Export
# --------------------------------------------------

reports = {
    "customer_activity_status.csv": customers,
    "activity_status_summary.csv": status,
    "monthly_active_customers.csv": monthly.assign(
        ActivityMonth=monthly["ActivityMonth"].astype(str)
    ),
    "reactivation_events.csv": reactivation_events.assign(
        ReactivationMonth=(
            reactivation_events["ReactivationMonth"]
            .astype(str)
        )
    ),
    "monthly_reactivations.csv": reactivation_monthly.assign(
        ReactivationMonth=(
            reactivation_monthly["ReactivationMonth"]
            .astype(str)
        )
    ),
    "monthly_customer_mix.csv": monthly_customer_mix.assign(
        ActivityMonth=(
            monthly_customer_mix["ActivityMonth"]
            .astype(str)
        )
    ),
    "customer_activity_summary.csv": summary
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

# --------------------------------------------------
# 8. Console
# --------------------------------------------------

print("=" * 65)
print("FOODPULSE 360 | CUSTOMER ACTIVITY INTELLIGENCE")
print("=" * 65)

print("\nACTIVITY STATUS")
print(status.round(2).to_string(index=False))

print("\nREACTIVATION SUMMARY")
print(summary.to_string(index=False))

print("\nLATEST 6 MONTHS")
print(
    monthly_customer_mix.tail(6).to_string(index=False)
)

print("\n[PASS] Customer, order and value totals reconciled.")
print("[PASS] First-observed customer counts reconciled.")
print("[PASS] Reactivation gaps validated.")
print("[SUCCESS] 7 reports generated.")