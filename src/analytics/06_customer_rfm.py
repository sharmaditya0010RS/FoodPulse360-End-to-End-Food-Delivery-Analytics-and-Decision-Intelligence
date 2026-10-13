from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"
OUTPUT = ROOT / "data/reports/customer_rfm"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    SOURCE,
    parse_dates=["order_date_clean"]
)

df["recorded_order_value"] = pd.to_numeric(
    df["recorded_order_value"],
    errors="raise"
)

df["confirmed_delivered_value"] = pd.to_numeric(
    df["confirmed_delivered_value"],
    errors="raise"
)

# --------------------------------------------------
# 1. Observation window
# --------------------------------------------------

observation_end = df["order_date_clean"].max()
snapshot_date = observation_end + pd.Timedelta(days=1)

# --------------------------------------------------
# 2. Customer-level observed behavior
# --------------------------------------------------

rfm = (
    df.groupby("CustomerID")
    .agg(
        CustomerCity=("customer_city", "first"),
        CustomerType=("customer_type", "first"),
        FirstOrderDate=("order_date_clean", "min"),
        LastOrderDate=("order_date_clean", "max"),
        Frequency=("OrderID", "nunique"),
        RecordedMonetary=("recorded_order_value", "sum"),
        DeliveredMonetary=("confirmed_delivered_value", "sum"),
        CancelledOrders=("is_cancelled", "sum"),
        DeliveredOrders=("is_delivered", "sum"),
        DelayedOrders=("is_delayed", "sum")
    )
    .reset_index()
)

rfm["RecencyDays"] = (
    snapshot_date - rfm["LastOrderDate"]
).dt.days

rfm["ObservedCustomerTenureDays"] = (
    rfm["LastOrderDate"] - rfm["FirstOrderDate"]
).dt.days + 1

rfm["AOV"] = (
    rfm["RecordedMonetary"] / rfm["Frequency"]
)

rfm["CancellationRatePct"] = (
    rfm["CancelledOrders"] / rfm["Frequency"] * 100
)

# --------------------------------------------------
# 3. RFM scoring
# Rank-based quantiles handle ties more consistently.
# Scores: 1 (low) to 5 (high).
# --------------------------------------------------

def quantile_score(series, ascending=True):
    ranks = series.rank(
        method="first",
        ascending=ascending
    )

    return pd.qcut(
        ranks,
        q=5,
        labels=[1, 2, 3, 4, 5]
    ).astype(int)


# Low recency is better
rfm["RScore"] = quantile_score(
    rfm["RecencyDays"],
    ascending=False
)

# High frequency is better
rfm["FScore"] = quantile_score(
    rfm["Frequency"],
    ascending=True
)

# High recorded monetary is better
rfm["MScore"] = quantile_score(
    rfm["RecordedMonetary"],
    ascending=True
)

rfm["RFMScore"] = (
    rfm["RScore"].astype(str)
    + rfm["FScore"].astype(str)
    + rfm["MScore"].astype(str)
)

rfm["TotalRFMScore"] = (
    rfm["RScore"] + rfm["FScore"] + rfm["MScore"]
)

# --------------------------------------------------
# 4. Mutually exclusive customer segments
# --------------------------------------------------

conditions = [
    (
        (rfm["RScore"] >= 4)
        & (rfm["FScore"] >= 4)
        & (rfm["MScore"] >= 4)
    ),
    (
        (rfm["RScore"] <= 2)
        & (rfm["FScore"] >= 4)
    ),
    (
        (rfm["RScore"] >= 4)
        & (rfm["FScore"] <= 2)
    ),
    (
        (rfm["RScore"] <= 2)
        & (rfm["FScore"] <= 2)
    ),
    (
        (rfm["FScore"] >= 4)
        & (rfm["MScore"] >= 4)
    )
]

labels = [
    "Champions",
    "At Risk",
    "Promising New/Occasional",
    "Low Engagement",
    "High Value Regulars"
]

rfm["Segment"] = np.select(
    conditions,
    labels,
    default="Core Customers"
)

# --------------------------------------------------
# 5. Segment-level summary
# --------------------------------------------------

segments = (
    rfm.groupby("Segment")
    .agg(
        Customers=("CustomerID", "count"),
        Orders=("Frequency", "sum"),
        RecordedMonetary=("RecordedMonetary", "sum"),
        DeliveredMonetary=("DeliveredMonetary", "sum"),
        MedianRecencyDays=("RecencyDays", "median"),
        AverageOrdersPerCustomer=("Frequency", "mean"),
        AverageCustomerValue=("RecordedMonetary", "mean")
    )
    .reset_index()
)

segments["CustomerSharePct"] = (
    segments["Customers"] / len(rfm) * 100
)

segments["RecordedValueSharePct"] = (
    segments["RecordedMonetary"]
    / rfm["RecordedMonetary"].sum() * 100
)

segments = segments.sort_values(
    "RecordedMonetary",
    ascending=False
)

# --------------------------------------------------
# 6. Customer frequency distribution
# --------------------------------------------------

rfm["FrequencyBand"] = pd.cut(
    rfm["Frequency"],
    bins=[0, 1, 3, 5, 10, 20, np.inf],
    labels=[
        "1 order",
        "2-3 orders",
        "4-5 orders",
        "6-10 orders",
        "11-20 orders",
        "21+ orders"
    ]
)

frequency = (
    rfm.groupby("FrequencyBand", observed=True)
    .agg(
        Customers=("CustomerID", "count"),
        Orders=("Frequency", "sum"),
        RecordedMonetary=("RecordedMonetary", "sum")
    )
    .reset_index()
)

# --------------------------------------------------
# 7. Reconciliation
# --------------------------------------------------

assert len(df) == 200000
assert len(rfm) == 20000
assert rfm["CustomerID"].is_unique

assert rfm["Frequency"].sum() == 200000

assert rfm["RecordedMonetary"].sum() == 164914494
assert rfm["DeliveredMonetary"].sum() == 132092968

assert rfm["CancelledOrders"].sum() == 19947
assert rfm["DeliveredOrders"].sum() == 160227
assert rfm["DelayedOrders"].sum() == 19826

assert segments["Customers"].sum() == 20000
assert segments["Orders"].sum() == 200000

assert segments["RecordedMonetary"].sum() == 164914494
assert frequency["Customers"].sum() == 20000

assert rfm["RScore"].between(1, 5).all()
assert rfm["FScore"].between(1, 5).all()
assert rfm["MScore"].between(1, 5).all()

# --------------------------------------------------
# 8. Export
# --------------------------------------------------

reports = {
    "customer_rfm_scorecard.csv": rfm,
    "rfm_segment_summary.csv": segments,
    "customer_frequency_distribution.csv": frequency,
    "top_100_customers.csv": rfm.sort_values(
        "RecordedMonetary",
        ascending=False
    ).head(100)
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

# --------------------------------------------------
# 9. Console
# --------------------------------------------------

print("=" * 65)
print("FOODPULSE 360 | CUSTOMER RFM INTELLIGENCE")
print("=" * 65)

print("\nOBSERVATION END:", observation_end.date())
print("SNAPSHOT DATE:", snapshot_date.date())

print("\nRFM SEGMENTS")
print(segments.round(2).to_string(index=False))

print("\nCUSTOMER FREQUENCY")
print(frequency.to_string(index=False))

print("\nCUSTOMER SUMMARY")
print("Total Customers:", len(rfm))
print("Total Orders:", int(rfm["Frequency"].sum()))
print(
    "Recorded Order Value:",
    int(rfm["RecordedMonetary"].sum())
)
print(
    "Delivered Order Value:",
    int(rfm["DeliveredMonetary"].sum())
)

print("\n[PASS] Customer and order totals reconciled.")
print("[PASS] Financial totals reconciled.")
print("[PASS] RFM scores and segments validated.")
print("[SUCCESS] 4 reports generated.")