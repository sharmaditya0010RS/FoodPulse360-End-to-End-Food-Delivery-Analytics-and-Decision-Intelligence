from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"
OUTPUT = ROOT / "data/reports/retention_validity"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(
    SOURCE,
    parse_dates=["order_date_clean"]
)

assert len(df) == 200000

# --------------------------------------------------
# 1. Customer first-observed order dates
# --------------------------------------------------

customers = (
    df.groupby("CustomerID")
    .agg(
        FirstOrder=("order_date_clean", "min"),
        LastOrder=("order_date_clean", "max"),
        Orders=("OrderID", "count")
    )
    .reset_index()
)

customers["CohortMonth"] = (
    customers["FirstOrder"].dt.to_period("M")
)

observation_start = df["order_date_clean"].min()
observation_end = df["order_date_clean"].max()

first_month = observation_start.to_period("M")
last_month = observation_end.to_period("M")

# --------------------------------------------------
# 2. Cohort size and boundary flags
# --------------------------------------------------

cohorts = (
    customers.groupby("CohortMonth")
    .agg(
        Customers=("CustomerID", "count"),
        AverageOrders=("Orders", "mean")
    )
    .reset_index()
)

cohorts["CustomerSharePct"] = (
    cohorts["Customers"] / len(customers) * 100
)

cohorts["IsFirstObservedMonth"] = (
    cohorts["CohortMonth"] == first_month
)

cohorts["IsLastObservedMonth"] = (
    cohorts["CohortMonth"] == last_month
)

cohorts["PotentialLeftCensoring"] = (
    cohorts["IsFirstObservedMonth"]
)

cohorts["IncompleteAcquisitionMonth"] = (
    cohorts["IsLastObservedMonth"]
)

# --------------------------------------------------
# 3. Cohort maturity
# --------------------------------------------------

cohorts["MonthsToObservationEnd"] = (
    (last_month.year - cohorts["CohortMonth"].dt.year) * 12
    + (last_month.month - cohorts["CohortMonth"].dt.month)
)

cohorts["HasCompleteMonth1"] = (
    cohorts["MonthsToObservationEnd"] >= 2
)

cohorts["HasCompleteMonth3"] = (
    cohorts["MonthsToObservationEnd"] >= 4
)

cohorts["HasCompleteMonth6"] = (
    cohorts["MonthsToObservationEnd"] >= 7
)

cohorts["HasCompleteMonth12"] = (
    cohorts["MonthsToObservationEnd"] >= 13
)

# --------------------------------------------------
# 4. First-observed-month distribution
# --------------------------------------------------

first_order_days = (
    customers.groupby("FirstOrder")
    .size()
    .reset_index(name="FirstObservedCustomers")
)

first_order_days["DaysSinceDatasetStart"] = (
    first_order_days["FirstOrder"] - observation_start
).dt.days

first_30_days = int(
    first_order_days.loc[
        first_order_days["DaysSinceDatasetStart"] < 30,
        "FirstObservedCustomers"
    ].sum()
)

first_90_days = int(
    first_order_days.loc[
        first_order_days["DaysSinceDatasetStart"] < 90,
        "FirstObservedCustomers"
    ].sum()
)

# --------------------------------------------------
# 5. Sensitivity: exclude first boundary cohort
# --------------------------------------------------

valid_cohorts = cohorts.loc[
    ~cohorts["PotentialLeftCensoring"]
    & ~cohorts["IncompleteAcquisitionMonth"]
].copy()

# This does not prove remaining cohorts are true
# acquisition cohorts. It only removes boundaries.

summary = pd.DataFrame([
    ["Total Customers", len(customers)],
    ["Observed Cohorts", len(cohorts)],
    ["Dataset Start", str(observation_start.date())],
    ["Dataset End", str(observation_end.date())],
    ["First 30 Days First-Observed Customers", first_30_days],
    ["First 90 Days First-Observed Customers", first_90_days],
    ["First Month Cohort Customers",
     int(cohorts.loc[
         cohorts["IsFirstObservedMonth"], "Customers"
     ].sum())],
    ["First Month Cohort Share Pct",
     cohorts.loc[
         cohorts["IsFirstObservedMonth"], "CustomerSharePct"
     ].sum()],
    ["Boundary-Excluded Cohorts", len(valid_cohorts)],
    ["Boundary-Excluded Customers",
     int(valid_cohorts["Customers"].sum())],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 6. Reconciliation
# --------------------------------------------------

assert len(customers) == 20000
assert customers["Orders"].sum() == 200000
assert cohorts["Customers"].sum() == 20000

assert first_30_days <= first_90_days <= 20000

assert (
    valid_cohorts["Customers"].sum()
    <= 20000
)

assert (
    cohorts["CustomerSharePct"].sum()
    - 100
) < 1e-8

# --------------------------------------------------
# 7. Export
# --------------------------------------------------

reports = {
    "cohort_validity_summary.csv": summary,
    "cohort_boundary_audit.csv": cohorts.assign(
        CohortMonth=cohorts["CohortMonth"].astype(str)
    ),
    "first_observed_order_distribution.csv": first_order_days,
    "boundary_excluded_cohorts.csv": valid_cohorts.assign(
        CohortMonth=valid_cohorts["CohortMonth"].astype(str)
    )
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | RETENTION VALIDITY AUDIT")
print("=" * 65)

print("\nVALIDITY SUMMARY")
print(summary.to_string(index=False))

print("\nFIRST 12 COHORTS")
print(
    cohorts.head(12)
    .round(2)
    .to_string(index=False)
)

print("\n[PASS] Customer and cohort totals reconciled.")
print("[PASS] Observation boundary checks completed.")
print("[SUCCESS] 4 reports generated.")