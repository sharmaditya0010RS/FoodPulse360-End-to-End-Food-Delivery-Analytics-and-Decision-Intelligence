from pathlib import Path
import calendar
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"
OUTPUT = ROOT / "data/reports/growth_validation"
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

df["month"] = df["order_date_clean"].dt.to_period("M")
df["day"] = df["order_date_clean"].dt.day

min_date = df["order_date_clean"].min()
max_date = df["order_date_clean"].max()

# --------------------------------------------------
# 1. Monthly performance with partial-month flags
# --------------------------------------------------

monthly = (
    df.groupby("month")
    .agg(
        Orders=("OrderID", "count"),
        RecordedValue=("recorded_order_value", "sum"),
        DeliveredValue=("confirmed_delivered_value", "sum")
    )
    .reset_index()
    .sort_values("month")
)

monthly["CalendarDays"] = monthly["month"].apply(
    lambda x: x.days_in_month
)

monthly["ObservedDays"] = monthly["CalendarDays"]

first_month = min_date.to_period("M")
last_month = max_date.to_period("M")

if first_month == last_month:
    monthly.loc[
        monthly["month"] == first_month, "ObservedDays"
    ] = max_date.day - min_date.day + 1
else:
    monthly.loc[
        monthly["month"] == first_month, "ObservedDays"
    ] = first_month.days_in_month - min_date.day + 1

    monthly.loc[
        monthly["month"] == last_month, "ObservedDays"
    ] = max_date.day

monthly["IsCompleteMonth"] = (
    monthly["ObservedDays"] == monthly["CalendarDays"]
)

monthly["OrdersPerDay"] = (
    monthly["Orders"] / monthly["ObservedDays"]
)

monthly["RecordedValuePerDay"] = (
    monthly["RecordedValue"] / monthly["ObservedDays"]
)

monthly["NaiveOrderMoMPct"] = (
    monthly["Orders"].pct_change() * 100
)

monthly["DailyRateMoMPct"] = (
    monthly["OrdersPerDay"].pct_change() * 100
)

monthly["DailyValueRateMoMPct"] = (
    monthly["RecordedValuePerDay"].pct_change() * 100
)

# --------------------------------------------------
# 2. Like-for-like comparison: September 1-26
#    versus August 1-26
# --------------------------------------------------

current_month = last_month
previous_month = current_month - 1

current_days = max_date.day

current = df.loc[
    df["month"] == current_month
]

previous = df.loc[
    (df["month"] == previous_month)
    & (df["day"] <= current_days)
]

comparison = pd.DataFrame([
    {
        "Period": f"{previous_month} days 1-{current_days}",
        "Orders": len(previous),
        "RecordedValue": previous["recorded_order_value"].sum(),
        "DeliveredValue": previous["confirmed_delivered_value"].sum(),
        "Days": current_days
    },
    {
        "Period": f"{current_month} days 1-{current_days}",
        "Orders": len(current),
        "RecordedValue": current["recorded_order_value"].sum(),
        "DeliveredValue": current["confirmed_delivered_value"].sum(),
        "Days": current_days
    }
])

previous_orders = len(previous)
current_orders = len(current)

previous_value = previous["recorded_order_value"].sum()
current_value = current["recorded_order_value"].sum()

order_growth = (
    (current_orders / previous_orders - 1) * 100
    if previous_orders else np.nan
)

value_growth = (
    (current_value / previous_value - 1) * 100
    if previous_value else np.nan
)

# --------------------------------------------------
# 3. Poisson rate-ratio confidence interval
#    Descriptive approximation, not causal proof
# --------------------------------------------------

rate_ratio = current_orders / previous_orders

log_se = np.sqrt(
    1 / current_orders + 1 / previous_orders
)

ci_low = np.exp(
    np.log(rate_ratio) - 1.96 * log_se
)

ci_high = np.exp(
    np.log(rate_ratio) + 1.96 * log_se
)

statistics = pd.DataFrame([
    ["Previous Period Orders", previous_orders],
    ["Current Period Orders", current_orders],
    ["Like-for-Like Order Growth Pct", order_growth],
    ["Like-for-Like Value Growth Pct", value_growth],
    ["Order Rate Ratio", rate_ratio],
    ["Approx 95% CI Lower", ci_low],
    ["Approx 95% CI Upper", ci_high],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 4. Calendar-day profile
# --------------------------------------------------

daily = (
    df.groupby("order_date_clean")
    .agg(
        Orders=("OrderID", "count"),
        RecordedValue=("recorded_order_value", "sum")
    )
    .reset_index()
)

daily["DayOfWeek"] = daily["order_date_clean"].dt.day_name()

weekday = (
    daily.groupby("DayOfWeek")
    .agg(
        Days=("order_date_clean", "count"),
        TotalOrders=("Orders", "sum"),
        AverageDailyOrders=("Orders", "mean"),
        AverageDailyValue=("RecordedValue", "mean")
    )
    .reset_index()
)

weekday_order = [
    "Monday", "Tuesday", "Wednesday",
    "Thursday", "Friday", "Saturday", "Sunday"
]

weekday["DayOfWeek"] = pd.Categorical(
    weekday["DayOfWeek"],
    categories=weekday_order,
    ordered=True
)

weekday = weekday.sort_values("DayOfWeek")

# --------------------------------------------------
# 5. Reconciliation
# --------------------------------------------------

assert len(df) == 200000

assert monthly["Orders"].sum() == 200000
assert daily["Orders"].sum() == 200000
assert weekday["TotalOrders"].sum() == 200000

assert monthly["RecordedValue"].sum() == 164914494
assert daily["RecordedValue"].sum() == 164914494

assert current_orders == 5168

assert monthly.loc[
    monthly["month"] == last_month,
    "ObservedDays"
].iloc[0] == 26

assert len(previous) > 0
assert len(current) > 0

# --------------------------------------------------
# 6. Export
# --------------------------------------------------

monthly["month"] = monthly["month"].astype(str)

reports = {
    "monthly_adjusted_growth.csv": monthly,
    "like_for_like_comparison.csv": comparison,
    "growth_statistics.csv": statistics,
    "weekday_performance.csv": weekday,
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | FAIR GROWTH VALIDATION")
print("=" * 65)

print("\nLATEST 3 MONTHS")
print(monthly.tail(3).round(2).to_string(index=False))

print("\nLIKE-FOR-LIKE COMPARISON")
print(comparison.to_string(index=False))

print("\nGROWTH STATISTICS")
print(statistics.round(4).to_string(index=False))

print("\nWEEKDAY PERFORMANCE")
print(weekday.round(2).to_string(index=False))

print("\n[PASS] Monthly, daily and weekday counts reconciled.")
print("[PASS] Financial values reconciled.")
print("[PASS] Partial-month adjustment applied.")
print("[SUCCESS] 4 reports saved.")