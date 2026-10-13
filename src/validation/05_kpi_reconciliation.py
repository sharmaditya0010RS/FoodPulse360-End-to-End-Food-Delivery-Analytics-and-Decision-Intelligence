from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/reports/kpi_reconciliation"
OUTPUT.mkdir(parents=True, exist_ok=True)

orders = pd.read_excel(SOURCE, sheet_name="Orders")

orders["OrderValue"] = pd.to_numeric(
    orders["OrderValue"], errors="raise"
)

orders["OrderStatus"] = (
    orders["OrderStatus"].astype("string").str.strip()
)

VALID_STATUSES = {"Delivered", "Delayed", "Cancelled"}

assert set(orders["OrderStatus"].dropna()) == VALID_STATUSES
assert orders["OrderStatus"].notna().all()
assert orders["OrderID"].is_unique

# --------------------------------------------------
# 1. Base metrics
# --------------------------------------------------

total_orders = len(orders)
total_value = orders["OrderValue"].sum()

delivered = orders["OrderStatus"].eq("Delivered")
delayed = orders["OrderStatus"].eq("Delayed")
cancelled = orders["OrderStatus"].eq("Cancelled")

delivered_orders = int(delivered.sum())
delayed_orders = int(delayed.sum())
cancelled_orders = int(cancelled.sum())

delivered_value = orders.loc[delivered, "OrderValue"].sum()
delayed_value = orders.loc[delayed, "OrderValue"].sum()
cancelled_value = orders.loc[cancelled, "OrderValue"].sum()

# --------------------------------------------------
# 2. Revenue scenarios
# --------------------------------------------------

# Conservative: only explicitly delivered orders
confirmed_delivered_value = delivered_value

# Alternative: delayed orders assumed completed
potential_completed_value = delivered_value + delayed_value

# Exposure: cancelled order face value, NOT proven loss
cancelled_value_exposure = cancelled_value

# --------------------------------------------------
# 3. KPI definitions
# --------------------------------------------------

kpis = {
    "Total Orders": total_orders,
    "Delivered Orders": delivered_orders,
    "Delayed Orders": delayed_orders,
    "Cancelled Orders": cancelled_orders,
    "Delivered Rate (%)": delivered_orders / total_orders * 100,
    "Delayed Rate (%)": delayed_orders / total_orders * 100,
    "Cancellation Rate (%)": cancelled_orders / total_orders * 100,
    "Recorded Order Value": total_value,
    "Delivered Order Value": confirmed_delivered_value,
    "Delivered Plus Delayed Value": potential_completed_value,
    "Cancelled Value Exposure": cancelled_value_exposure,
    "Overall Average Order Value": total_value / total_orders,
    "Delivered Average Order Value": (
        delivered_value / delivered_orders
    ),
}

report = pd.DataFrame(
    kpis.items(),
    columns=["KPI", "Value"]
)

# --------------------------------------------------
# 4. Independent reconciliation
# --------------------------------------------------

status_counts = orders.groupby("OrderStatus").size()
status_values = orders.groupby("OrderStatus")["OrderValue"].sum()

assert int(status_counts.sum()) == total_orders
assert int(status_counts["Delivered"]) == delivered_orders
assert int(status_counts["Delayed"]) == delayed_orders
assert int(status_counts["Cancelled"]) == cancelled_orders

assert abs(float(status_values.sum()) - float(total_value)) < 0.01

assert abs(
    float(delivered_value + delayed_value + cancelled_value)
    - float(total_value)
) < 0.01

assert abs(
    sum([
        kpis["Delivered Rate (%)"],
        kpis["Delayed Rate (%)"],
        kpis["Cancellation Rate (%)"]
    ]) - 100
) < 1e-9

# --------------------------------------------------
# 5. Export
# --------------------------------------------------

report.to_csv(
    OUTPUT / "kpi_baseline.csv",
    index=False,
    encoding="utf-8-sig"
)

status_summary = (
    orders.groupby("OrderStatus")
    .agg(
        Orders=("OrderID", "count"),
        OrderValue=("OrderValue", "sum")
    )
    .reset_index()
)

status_summary.to_csv(
    OUTPUT / "status_reconciliation.csv",
    index=False,
    encoding="utf-8-sig"
)

print("=" * 60)
print("FOODPULSE 360 | KPI RECONCILIATION")
print("=" * 60)

print(report.round(2).to_string(index=False))

print("\n[PASS] Order counts reconciled.")
print("[PASS] Order values reconciled.")
print("[PASS] Status percentages sum to 100%.")
print("[SUCCESS] 2 reports saved.")