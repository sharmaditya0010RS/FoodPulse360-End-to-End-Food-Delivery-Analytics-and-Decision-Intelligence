from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"
OUTPUT = ROOT / "data/reports/customer_retention"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    SOURCE,
    parse_dates=["order_date_clean"]
)

assert len(df) == 200000
assert df["OrderID"].is_unique

# --------------------------------------------------
# 1. Observed customer behavior
# --------------------------------------------------

customer = (
    df.groupby("CustomerID")
    .agg(
        FirstObservedOrder=("order_date_clean", "min"),
        LastObservedOrder=("order_date_clean", "max"),
        TotalOrders=("OrderID", "count"),
        ActiveOrderDates=("order_date_clean", "nunique"),
        RecordedValue=("recorded_order_value", "sum")
    )
    .reset_index()
)

customer["RepeatCustomer"] = (
    customer["TotalOrders"] >= 2
)

customer["MultiDayCustomer"] = (
    customer["ActiveOrderDates"] >= 2
)

customer["ObservedSpanDays"] = (
    customer["LastObservedOrder"]
    - customer["FirstObservedOrder"]
).dt.days

# --------------------------------------------------
# 2. First observed order cohorts
# --------------------------------------------------

df = df.merge(
    customer[["CustomerID", "FirstObservedOrder"]],
    on="CustomerID",
    how="left",
    validate="many_to_one"
)

df["CohortMonth"] = (
    df["FirstObservedOrder"].dt.to_period("M")
)

df["ActivityMonth"] = (
    df["order_date_clean"].dt.to_period("M")
)

df["CohortAgeMonths"] = (
    (df["ActivityMonth"].dt.year - df["CohortMonth"].dt.year)
    * 12
    + (df["ActivityMonth"].dt.month - df["CohortMonth"].dt.month)
)

assert (df["CohortAgeMonths"] >= 0).all()

# Customer active at least once in each observed month
activity = (
    df.groupby(["CohortMonth", "CohortAgeMonths"])
    ["CustomerID"]
    .nunique()
    .reset_index(name="ActiveCustomers")
)

cohort_sizes = (
    customer.assign(
        CohortMonth=customer[
            "FirstObservedOrder"
        ].dt.to_period("M")
    )
    .groupby("CohortMonth")
    .size()
    .reset_index(name="CohortSize")
)

activity = activity.merge(
    cohort_sizes,
    on="CohortMonth",
    validate="many_to_one"
)

activity["RetentionRatePct"] = (
    activity["ActiveCustomers"]
    / activity["CohortSize"]
    * 100
)

# --------------------------------------------------
# 3. Handle right-censoring
# --------------------------------------------------

observation_end = df["order_date_clean"].max()
last_month = observation_end.to_period("M")

activity["MonthsAvailable"] = (
    (last_month.year - activity["CohortMonth"].dt.year)
    * 12
    + (last_month.month - activity["CohortMonth"].dt.month)
)

activity["CohortMonthComplete"] = (
    activity["CohortMonth"] < last_month
)

activity["ActivityMonth"] = (
    activity["CohortMonth"]
    + activity["CohortAgeMonths"]
)

activity["ActivityMonthComplete"] = (
    activity["ActivityMonth"] < last_month
)

# For a fair monthly retention analysis, exclude
# the incomplete September 2025 activity month.

complete_activity = activity.loc[
    activity["ActivityMonthComplete"]
].copy()

# --------------------------------------------------
# 4. Monthly cohort retention matrix
# --------------------------------------------------

retention_matrix = complete_activity.pivot(
    index="CohortMonth",
    columns="CohortAgeMonths",
    values="RetentionRatePct"
)

retention_matrix = retention_matrix.reindex(
    columns=range(int(activity["CohortAgeMonths"].max()) + 1)
)

# Preserve unavailable cells as NaN (not zero)
retention_matrix.index = retention_matrix.index.astype(str)
retention_matrix.columns = [
    f"Month_{x}" for x in retention_matrix.columns
]

# --------------------------------------------------
# 5. Weighted retention at fixed cohort ages
# --------------------------------------------------

# Only include cohorts with a complete target month.
# Explicitly construct eligible cohort denominators,
# including cohorts with zero returning customers.

cohort_sizes["CohortMonth"] = (
    cohort_sizes["CohortMonth"].astype(str)
)

complete_activity["CohortMonth"] = (
    complete_activity["CohortMonth"].astype(str)
)

weighted_rows = []

for age in [1, 2, 3, 6, 12]:
    eligible = cohort_sizes.copy()

    eligible["TargetMonth"] = pd.Series(
        [
            pd.Period(month, freq="M") + age
            for month in eligible["CohortMonth"]
        ],
        index=eligible.index,
        dtype="period[M]"
    )

    eligible = eligible.loc[
        eligible["TargetMonth"] < last_month
    ].copy()

    matching = complete_activity.loc[
        complete_activity["CohortAgeMonths"] == age,
        ["CohortMonth", "ActiveCustomers"]
    ]

    eligible = eligible.merge(
        matching,
        on="CohortMonth",
        how="left",
        validate="one_to_one"
    )

    eligible["ActiveCustomers"] = (
        eligible["ActiveCustomers"].fillna(0)
    )

    denominator = eligible["CohortSize"].sum()
    numerator = eligible["ActiveCustomers"].sum()

    weighted_rows.append({
        "CohortAgeMonths": age,
        "EligibleCohorts": len(eligible),
        "EligibleCustomers": int(denominator),
        "ActiveCustomers": int(numerator),
        "WeightedRetentionPct": (
            numerator / denominator * 100
            if denominator else np.nan
        )
    })

weighted = pd.DataFrame(weighted_rows)

# --------------------------------------------------
# 6. Repeat behavior summary
# --------------------------------------------------

summary = pd.DataFrame([
    ["Total Customers", len(customer)],
    ["Total Orders", len(df)],
    ["Customers With 2+ Orders",
     int(customer["RepeatCustomer"].sum())],
    ["Customers Active On 2+ Dates",
     int(customer["MultiDayCustomer"].sum())],
    ["Repeat Customer Rate Pct",
     customer["RepeatCustomer"].mean() * 100],
    ["Multi-Day Customer Rate Pct",
     customer["MultiDayCustomer"].mean() * 100],
    ["Median Orders Per Customer",
     customer["TotalOrders"].median()],
    ["Median Observed Span Days",
     customer["ObservedSpanDays"].median()],
    ["Observed Cohorts", len(cohort_sizes)],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 7. Reconciliation
# --------------------------------------------------

assert len(customer) == 20000
assert customer["CustomerID"].is_unique
assert customer["TotalOrders"].sum() == 200000

assert customer["RecordedValue"].sum() == 164914494

assert cohort_sizes["CohortSize"].sum() == 20000

assert (
    activity.loc[
        activity["CohortAgeMonths"] == 0,
        "ActiveCustomers"
    ].sum() == 20000
)

assert activity["RetentionRatePct"].between(0, 100).all()

assert (
    weighted["ActiveCustomers"]
    <= weighted["EligibleCustomers"]
).all()

# --------------------------------------------------
# 8. Export
# --------------------------------------------------

reports = {
    "customer_repeat_behavior.csv": customer,
    "repeat_behavior_summary.csv": summary,
    "observed_order_cohort_sizes.csv": cohort_sizes,
    "monthly_cohort_activity.csv": activity.assign(
        CohortMonth=activity["CohortMonth"].astype(str),
        ActivityMonth=activity["ActivityMonth"].astype(str)
    ),
    "cohort_retention_matrix.csv": (
        retention_matrix.reset_index()
    ),
    "weighted_retention.csv": weighted
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | CUSTOMER RETENTION")
print("=" * 65)

print("\nREPEAT BEHAVIOR")
print(summary.round(2).to_string(index=False))

print("\nWEIGHTED COHORT RETENTION")
print(weighted.round(2).to_string(index=False))

print("\nFIRST 8 COHORT SIZES")
print(cohort_sizes.head(8).to_string(index=False))

print("\n[PASS] Customer, order and value totals reconciled.")
print("[PASS] Cohort denominators reconciled.")
print("[PASS] Incomplete activity month excluded from retention matrix.")
print("[SUCCESS] 6 reports generated.")