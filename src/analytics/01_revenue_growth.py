from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"
OUTPUT = ROOT / "data/reports/revenue_growth"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    SOURCE,
    parse_dates=["order_date_clean"]
)

df["recorded_order_value"] = pd.to_numeric(
    df["recorded_order_value"], errors="raise"
)

df["confirmed_delivered_value"] = pd.to_numeric(
    df["confirmed_delivered_value"], errors="raise"
)

df["order_month_key"] = (
    df["order_date_clean"].dt.to_period("M").astype(str)
)

# --------------------------------------------------
# 1. Monthly performance
# --------------------------------------------------

monthly = (
    df.groupby("order_month_key")
    .agg(
        TotalOrders=("OrderID", "count"),
        UniqueCustomers=("CustomerID", "nunique"),
        ActiveRestaurants=("RestaurantID", "nunique"),
        RecordedOrderValue=("recorded_order_value", "sum"),
        DeliveredOrderValue=("confirmed_delivered_value", "sum"),
        DeliveredOrders=("is_delivered", "sum"),
        CancelledOrders=("is_cancelled", "sum"),
        DelayedOrders=("is_delayed", "sum")
    )
    .reset_index()
    .sort_values("order_month_key")
)

monthly["AOV"] = (
    monthly["RecordedOrderValue"] / monthly["TotalOrders"]
)

monthly["CancellationRatePct"] = (
    monthly["CancelledOrders"] / monthly["TotalOrders"] * 100
)

monthly["DeliveredRatePct"] = (
    monthly["DeliveredOrders"] / monthly["TotalOrders"] * 100
)

monthly["OrderGrowthMoMPct"] = (
    monthly["TotalOrders"].pct_change() * 100
)

monthly["ValueGrowthMoMPct"] = (
    monthly["RecordedOrderValue"].pct_change() * 100
)

# --------------------------------------------------
# 2. Yearly performance
# --------------------------------------------------

yearly = (
    df.groupby("order_year")
    .agg(
        TotalOrders=("OrderID", "count"),
        UniqueCustomers=("CustomerID", "nunique"),
        RecordedOrderValue=("recorded_order_value", "sum"),
        DeliveredOrderValue=("confirmed_delivered_value", "sum")
    )
    .reset_index()
)

yearly["AOV"] = (
    yearly["RecordedOrderValue"] / yearly["TotalOrders"]
)

# --------------------------------------------------
# 3. Daily performance
# --------------------------------------------------

daily = (
    df.groupby("order_date_clean")
    .agg(
        TotalOrders=("OrderID", "count"),
        RecordedOrderValue=("recorded_order_value", "sum"),
        DeliveredOrderValue=("confirmed_delivered_value", "sum")
    )
    .reset_index()
)

# --------------------------------------------------
# 4. Executive KPI summary
# --------------------------------------------------

summary = pd.DataFrame([
    ["Total Orders", len(df)],
    ["Unique Customers", df["CustomerID"].nunique()],
    ["Active Restaurants", df["RestaurantID"].nunique()],
    ["Recorded Order Value", df["recorded_order_value"].sum()],
    ["Delivered Order Value", df["confirmed_delivered_value"].sum()],
    ["Overall AOV", df["recorded_order_value"].mean()],
    ["Cancellation Rate Pct", df["is_cancelled"].mean() * 100],
    ["Delivered Rate Pct", df["is_delivered"].mean() * 100],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 5. Independent reconciliation
# --------------------------------------------------

assert len(df) == 200000

assert monthly["TotalOrders"].sum() == len(df)
assert yearly["TotalOrders"].sum() == len(df)
assert daily["TotalOrders"].sum() == len(df)

assert monthly["RecordedOrderValue"].sum() == 164914494
assert yearly["RecordedOrderValue"].sum() == 164914494
assert daily["RecordedOrderValue"].sum() == 164914494

assert monthly["DeliveredOrderValue"].sum() == 132092968
assert yearly["DeliveredOrderValue"].sum() == 132092968
assert daily["DeliveredOrderValue"].sum() == 132092968

# --------------------------------------------------
# 6. Export
# --------------------------------------------------

reports = {
    "monthly_performance.csv": monthly,
    "yearly_performance.csv": yearly,
    "daily_performance.csv": daily,
    "executive_kpis.csv": summary,
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | REVENUE & GROWTH BASELINE")
print("=" * 65)

print("\nEXECUTIVE KPIs")
print(summary.round(2).to_string(index=False))

print("\nYEARLY PERFORMANCE")
print(yearly.round(2).to_string(index=False))

print("\nLATEST 6 MONTHS")
print(monthly.tail(6).round(2).to_string(index=False))

print("\n[PASS] Daily, monthly and yearly order totals reconciled.")
print("[PASS] Recorded order values reconciled.")
print("[PASS] Delivered order values reconciled.")
print("[SUCCESS] 4 analytics reports generated.")