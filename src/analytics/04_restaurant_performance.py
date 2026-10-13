from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"
OUTPUT = ROOT / "data/reports/restaurant_performance"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(SOURCE)

df["recorded_order_value"] = pd.to_numeric(
    df["recorded_order_value"], errors="raise"
)

df["confirmed_delivered_value"] = pd.to_numeric(
    df["confirmed_delivered_value"], errors="raise"
)

df["restaurant_quality_flag"] = (
    df["restaurant_quality_flag"]
    .astype("string")
    .str.lower()
    .eq("true")
    .fillna(True)
)

df["is_cancelled"] = (
    df["order_status_clean"] == "Cancelled"
)

df["is_delayed"] = (
    df["order_status_clean"] == "Delayed"
)

df["is_delivered"] = (
    df["order_status_clean"] == "Delivered"
)

# 1. Restaurant-level performance
restaurants = (
    df.groupby("RestaurantID")
    .agg(
        RestaurantName=("restaurant_name", "first"),
        Location=("restaurant_location", "first"),
        QualityFlag=("restaurant_quality_flag", "max"),
        Orders=("OrderID", "count"),
        UniqueCustomers=("CustomerID", "nunique"),
        RecordedValue=("recorded_order_value", "sum"),
        DeliveredValue=("confirmed_delivered_value", "sum"),
        CancelledOrders=("is_cancelled", "sum"),
        DelayedOrders=("is_delayed", "sum"),
        DeliveredOrders=("is_delivered", "sum")
    )
    .reset_index()
)

restaurants["AOV"] = (
    restaurants["RecordedValue"] / restaurants["Orders"]
)

restaurants["CancellationRatePct"] = (
    restaurants["CancelledOrders"] / restaurants["Orders"] * 100
)

restaurants["DeliveredRatePct"] = (
    restaurants["DeliveredOrders"] / restaurants["Orders"] * 100
)

restaurants = restaurants.sort_values(
    ["RecordedValue", "RestaurantID"],
    ascending=[False, True]
).reset_index(drop=True)

restaurants["ValueRank"] = np.arange(
    1, len(restaurants) + 1
)

# 2. Concentration analysis
total_value = restaurants["RecordedValue"].sum()
total_restaurants = len(restaurants)

concentration_rows = []

for pct in [1, 5, 10, 20]:
    count = max(
        1, int(np.ceil(total_restaurants * pct / 100))
    )

    top = restaurants.head(count)

    concentration_rows.append({
        "TopRestaurantPct": pct,
        "RestaurantCount": count,
        "RecordedValue": top["RecordedValue"].sum(),
        "ValueSharePct": (
            top["RecordedValue"].sum() / total_value * 100
        ),
        "OrderSharePct": (
            top["Orders"].sum() / len(df) * 100
        )
    })

concentration = pd.DataFrame(concentration_rows)

# 3. Order-volume distribution
restaurants["VolumeBand"] = pd.cut(
    restaurants["Orders"],
    bins=[0, 1, 2, 5, 10, 25, np.inf],
    labels=[
        "1 order",
        "2 orders",
        "3-5 orders",
        "6-10 orders",
        "11-25 orders",
        "26+ orders"
    ]
)

volume_distribution = (
    restaurants.groupby("VolumeBand", observed=True)
    .agg(
        Restaurants=("RestaurantID", "count"),
        Orders=("Orders", "sum"),
        RecordedValue=("RecordedValue", "sum")
    )
    .reset_index()
)

volume_distribution["RestaurantSharePct"] = (
    volume_distribution["Restaurants"]
    / total_restaurants * 100
)

# 4. Quality-flag sensitivity
quality = (
    restaurants.groupby("QualityFlag")
    .agg(
        Restaurants=("RestaurantID", "count"),
        Orders=("Orders", "sum"),
        RecordedValue=("RecordedValue", "sum"),
        CancelledOrders=("CancelledOrders", "sum")
    )
    .reset_index()
)

quality["CancellationRatePct"] = (
    quality["CancelledOrders"] / quality["Orders"] * 100
)

# 5. High-volume restaurant performance
# Minimum 10 orders avoids ranking 1-order restaurants
high_volume = restaurants.loc[
    (restaurants["Orders"] >= 10)
    & (~restaurants["QualityFlag"])
].copy()

high_volume = high_volume.sort_values(
    ["CancellationRatePct", "Orders"],
    ascending=[False, False]
)

# 6. Checks
assert len(df) == 200000
assert len(restaurants) == 54600

assert restaurants["Orders"].sum() == 200000
assert restaurants["RecordedValue"].sum() == 164914494
assert restaurants["DeliveredValue"].sum() == 132092968

assert restaurants["CancelledOrders"].sum() == 19947
assert restaurants["DelayedOrders"].sum() == 19826
assert restaurants["DeliveredOrders"].sum() == 160227

assert quality["Orders"].sum() == 200000
assert volume_distribution["Orders"].sum() == 200000
assert volume_distribution["Restaurants"].sum() == 54600

assert (
    quality.loc[
        quality["QualityFlag"], "Orders"
    ].sum() == 15859
)

# 7. Export
reports = {
    "restaurant_scorecard.csv": restaurants,
    "restaurant_concentration.csv": concentration,
    "restaurant_volume_distribution.csv": volume_distribution,
    "restaurant_quality_sensitivity.csv": quality,
    "high_volume_cancellation_watchlist.csv": high_volume,
    "top_20_restaurants.csv": restaurants.head(20)
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | RESTAURANT PERFORMANCE")
print("=" * 65)

print("\nCONCENTRATION")
print(concentration.round(2).to_string(index=False))

print("\nORDER VOLUME DISTRIBUTION")
print(volume_distribution.round(2).to_string(index=False))

print("\nQUALITY SENSITIVITY")
print(quality.round(2).to_string(index=False))

print("\nTOP 10 RESTAURANTS")
print(
    restaurants[
        [
            "RestaurantID", "RestaurantName",
            "Orders", "RecordedValue",
            "CancellationRatePct", "QualityFlag"
        ]
    ].head(10).round(2).to_string(index=False)
)

print("\nHIGH-VOLUME WATCHLIST COUNT:", len(high_volume))

print("\n[PASS] Restaurant-level metrics reconciled.")
print("[PASS] Concentration and volume totals reconciled.")
print("[PASS] Quality-flag exposure reconciled.")
print("[SUCCESS] 6 reports saved.")