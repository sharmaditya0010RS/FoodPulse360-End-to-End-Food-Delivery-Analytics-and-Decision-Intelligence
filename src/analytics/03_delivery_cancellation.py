from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency, mannwhitneyu

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"
OUTPUT = ROOT / "data/reports/delivery_cancellation"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(SOURCE)

df["order_value_clean"] = pd.to_numeric(
    df["order_value_clean"], errors="raise"
)

df["delivery_mins_clean"] = pd.to_numeric(
    df["delivery_mins_clean"], errors="raise"
)

df["is_cancelled"] = (
    df["order_status_clean"] == "Cancelled"
)

df["is_delivered"] = (
    df["order_status_clean"] == "Delivered"
)

df["is_delayed"] = (
    df["order_status_clean"] == "Delayed"
)

# --------------------------------------------------
# 1. Overall operational KPIs
# --------------------------------------------------

total = len(df)
cancelled = int(df["is_cancelled"].sum())
delayed = int(df["is_delayed"].sum())
delivered = int(df["is_delivered"].sum())

overall = pd.DataFrame([
    ["Total Orders", total],
    ["Cancelled Orders", cancelled],
    ["Delayed Orders", delayed],
    ["Delivered Orders", delivered],
    ["Cancellation Rate Pct", cancelled / total * 100],
    ["Delayed Status Rate Pct", delayed / total * 100],
    ["Delivered Rate Pct", delivered / total * 100],
    ["Median Recorded Duration",
     df["delivery_mins_clean"].median()],
    ["Cancelled Recorded Value",
     df.loc[df["is_cancelled"], "order_value_clean"].sum()],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 2. Monthly cancellation trend
# --------------------------------------------------

df["order_month_key"] = (
    pd.to_datetime(df["order_date_clean"])
    .dt.to_period("M")
    .astype(str)
)

monthly = (
    df.groupby("order_month_key")
    .agg(
        Orders=("OrderID", "count"),
        Cancelled=("is_cancelled", "sum"),
        Delayed=("is_delayed", "sum"),
        Delivered=("is_delivered", "sum")
    )
    .reset_index()
)

monthly["CancellationRatePct"] = (
    monthly["Cancelled"] / monthly["Orders"] * 100
)

monthly["DelayedRatePct"] = (
    monthly["Delayed"] / monthly["Orders"] * 100
)

# --------------------------------------------------
# 3. Order value bands
# --------------------------------------------------

df["ValueBand"] = pd.cut(
    df["order_value_clean"],
    bins=[-np.inf, 500, 1000, 1500, np.inf],
    labels=[
        "Up to 500",
        "501-1000",
        "1001-1500",
        "Above 1500"
    ]
)

value_bands = (
    df.groupby("ValueBand", observed=True)
    .agg(
        Orders=("OrderID", "count"),
        Cancelled=("is_cancelled", "sum"),
        Delayed=("is_delayed", "sum"),
        MedianDuration=("delivery_mins_clean", "median")
    )
    .reset_index()
)

value_bands["CancellationRatePct"] = (
    value_bands["Cancelled"] / value_bands["Orders"] * 100
)

# --------------------------------------------------
# 4. Chi-square: value band vs cancellation
# --------------------------------------------------

contingency = pd.crosstab(
    df["ValueBand"],
    df["is_cancelled"]
)

chi2_stat_raw, p_value_raw, dof_raw, expected = chi2_contingency(contingency)
chi2_stat = float(np.asarray(chi2_stat_raw).item())
p_value = float(np.asarray(p_value_raw).item())
expected = np.asarray(expected, dtype=float)
dof = int(np.asarray(dof_raw).item())

cramers_v = float(np.sqrt(
    chi2_stat / (
        total * min(contingency.shape[0] - 1,
                    contingency.shape[1] - 1)
    )
))

# --------------------------------------------------
# 5. Duration comparison: cancelled vs delivered
# --------------------------------------------------

cancel_duration = df.loc[
    df["is_cancelled"], "delivery_mins_clean"
]

delivered_duration = df.loc[
    df["is_delivered"], "delivery_mins_clean"
]

u_stat, duration_p = mannwhitneyu(
    cancel_duration,
    delivered_duration,
    alternative="two-sided"
)

stats = pd.DataFrame([
    ["Value Band Chi-square", chi2_stat],
    ["Value Band P-value", p_value],
    ["Value Band Cramers V", cramers_v],
    ["Duration Mann-Whitney U", u_stat],
    ["Duration P-value", duration_p],
    ["Cancelled Median Duration", cancel_duration.median()],
    ["Delivered Median Duration", delivered_duration.median()],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 6. Restaurant contamination sensitivity
# --------------------------------------------------

df["restaurant_quality_flag"] = (
    df["restaurant_quality_flag"]
    .astype("string").str.lower().eq("true")
)

sensitivity = (
    df.groupby("restaurant_quality_flag")
    .agg(
        Orders=("OrderID", "count"),
        Cancelled=("is_cancelled", "sum"),
        Delayed=("is_delayed", "sum")
    )
    .reset_index()
)

sensitivity["CancellationRatePct"] = (
    sensitivity["Cancelled"] / sensitivity["Orders"] * 100
)

# --------------------------------------------------
# 7. Reconciliation
# --------------------------------------------------

assert total == 200000
assert cancelled == 19947
assert delayed == 19826
assert delivered == 160227

assert monthly["Orders"].sum() == total
assert value_bands["Orders"].sum() == total
assert sensitivity["Orders"].sum() == total

assert int(monthly["Cancelled"].sum()) == cancelled

# --------------------------------------------------
# 8. Export
# --------------------------------------------------

reports = {
    "operational_kpis.csv": overall,
    "monthly_operations.csv": monthly,
    "order_value_bands.csv": value_bands,
    "statistical_tests.csv": stats,
    "restaurant_quality_sensitivity.csv": sensitivity,
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | DELIVERY & CANCELLATION ANALYSIS")
print("=" * 65)

print("\nOVERALL KPIs")
print(overall.round(2).to_string(index=False))

print("\nORDER VALUE BANDS")
print(value_bands.round(2).to_string(index=False))

print("\nSTATISTICAL TESTS")
print(stats.round(6).to_string(index=False))

print("\nQUALITY SENSITIVITY")
print(sensitivity.round(2).to_string(index=False))

print("\n[PASS] Operational totals reconciled.")
print("[PASS] Segmentation totals reconciled.")
print("[SUCCESS] 5 reports saved.")