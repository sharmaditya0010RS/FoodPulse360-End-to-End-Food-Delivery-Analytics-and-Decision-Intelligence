from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/reports/order_quality"
OUTPUT.mkdir(parents=True, exist_ok=True)

orders = pd.read_excel(SOURCE, sheet_name="Orders")

NUMERIC_COLUMNS = [
    "OrderValue",
    "DeliveryTimeMins",
    "Quantity"
]

for col in NUMERIC_COLUMNS:
    orders[col] = pd.to_numeric(orders[col], errors="coerce")

orders["OrderDate"] = pd.to_datetime(
    orders["OrderDate"], errors="coerce"
)

total = len(orders)

# --------------------------------------------------
# 1. Financial and operational quality checks
# --------------------------------------------------

checks = {
    "Total Orders": total,
    "Missing Order Value": orders["OrderValue"].isna().sum(),
    "Zero Order Value": (orders["OrderValue"] == 0).sum(),
    "Negative Order Value": (orders["OrderValue"] < 0).sum(),
    "Missing Quantity": orders["Quantity"].isna().sum(),
    "Zero Quantity": (orders["Quantity"] == 0).sum(),
    "Negative Quantity": (orders["Quantity"] < 0).sum(),
    "Missing Delivery Time": orders["DeliveryTimeMins"].isna().sum(),
    "Zero Delivery Time": (orders["DeliveryTimeMins"] == 0).sum(),
    "Negative Delivery Time": (orders["DeliveryTimeMins"] < 0).sum(),
    "Delivery Time Over 120 Mins": (
        orders["DeliveryTimeMins"] > 120
    ).sum(),
    "Invalid Order Dates": orders["OrderDate"].isna().sum(),
    "Unique Order Statuses": orders["OrderStatus"].nunique(),
}

quality = pd.DataFrame(
    checks.items(),
    columns=["Metric", "Count"]
)

# --------------------------------------------------
# 2. Order status distribution
# --------------------------------------------------

status = (
    orders.groupby("OrderStatus", dropna=False)
    .agg(
        Orders=("OrderID", "count"),
        OrderValue=("OrderValue", "sum"),
        AverageOrderValue=("OrderValue", "mean"),
        AverageDeliveryMins=("DeliveryTimeMins", "mean")
    )
    .reset_index()
)

status["OrderSharePct"] = (
    status["Orders"] / total * 100
).round(2)

# --------------------------------------------------
# 3. Numeric distributions
# --------------------------------------------------

numeric = (
    orders[NUMERIC_COLUMNS]
    .describe(percentiles=[0.01, 0.25, 0.5, 0.75, 0.95, 0.99])
    .T
    .reset_index()
    .rename(columns={"index": "Metric"})
)

# --------------------------------------------------
# 4. Status-specific delivery checks
# --------------------------------------------------

delivery = (
    orders.groupby("OrderStatus", dropna=False)
    .agg(
        Orders=("OrderID", "count"),
        ZeroDeliveryTime=(
            "DeliveryTimeMins",
            lambda x: (x == 0).sum()
        ),
        Over120Mins=(
            "DeliveryTimeMins",
            lambda x: (x > 120).sum()
        ),
        MedianDeliveryMins=("DeliveryTimeMins", "median")
    )
    .reset_index()
)

# --------------------------------------------------
# 5. Financial reconciliation
# --------------------------------------------------

total_order_value = orders["OrderValue"].sum()
status_order_value = status["OrderValue"].sum()

assert status["Orders"].sum() == total
assert abs(total_order_value - status_order_value) < 0.01
assert delivery["Orders"].sum() == total

# --------------------------------------------------
# 6. Save evidence
# --------------------------------------------------

reports = {
    "quality_checks.csv": quality,
    "status_distribution.csv": status,
    "numeric_distribution.csv": numeric,
    "delivery_by_status.csv": delivery,
}

for name, df in reports.items():
    df.to_csv(
        OUTPUT / name,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 60)
print("FOODPULSE 360 | ORDER QUALITY VALIDATION")
print("=" * 60)

print("\nQUALITY CHECKS")
print(quality.to_string(index=False))

print("\nORDER STATUS")
print(status.round(2).to_string(index=False))

print("\nDELIVERY BY STATUS")
print(delivery.to_string(index=False))

print(f"\nTotal Recorded Order Value: {total_order_value:,.2f}")
print("[PASS] Order counts reconciled.")
print("[PASS] Financial totals reconciled.")
print("[SUCCESS] 4 reports saved.")