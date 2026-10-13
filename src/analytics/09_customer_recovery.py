from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
PROCESSED = ROOT / "data/processed"
REPORTS = ROOT / "data/reports"
OUTPUT = REPORTS / "customer_recovery"
OUTPUT.mkdir(parents=True, exist_ok=True)

activity = pd.read_csv(
    REPORTS / "customer_activity/customer_activity_status.csv"
)

rfm = pd.read_csv(
    REPORTS / "rfm_stability/stable_customer_rfm.csv"
)

# --------------------------------------------------
# 1. Validate source datasets
# --------------------------------------------------

assert len(activity) == 20000
assert len(rfm) == 20000

assert activity["CustomerID"].is_unique
assert rfm["CustomerID"].is_unique

# --------------------------------------------------
# 2. Merge stable RFM with activity
# --------------------------------------------------

rfm_fields = rfm[
    [
        "CustomerID",
        "StableSegment",
        "RScoreStable",
        "FScoreStable",
        "MScoreStable",
        "DeliveredMonetary",
        "Frequency"
    ]
].rename(columns={
    "DeliveredMonetary": "HistoricalDeliveredValue",
    "Frequency": "HistoricalOrderCount"
})

customers = activity.merge(
    rfm_fields,
    on="CustomerID",
    how="left",
    validate="one_to_one",
    indicator=True
)

assert customers["_merge"].eq("both").all()

customers = customers.drop(columns="_merge")

# --------------------------------------------------
# 3. Define analytical recovery candidates
# --------------------------------------------------

# Inactive for >90 days AND historically high-value.
# This is a screening rule, not a churn prediction.

customers["Inactive90Plus"] = (
    customers["DaysSinceLastOrder"] > 90
)

customers["HistoricallyHighValue"] = (
    customers["MScoreStable"] >= 4
)

customers["RecoveryCandidate"] = (
    customers["Inactive90Plus"]
    & customers["HistoricallyHighValue"]
)

# More restrictive group:
# high monetary score + high frequency score

customers["PriorityRecoveryCandidate"] = (
    customers["RecoveryCandidate"]
    & (customers["FScoreStable"] >= 4)
)

# --------------------------------------------------
# 4. Candidate summary
# --------------------------------------------------

candidate_summary = pd.DataFrame([
    [
        "Total Customers",
        len(customers)
    ],
    [
        "Inactive >90 Days",
        int(customers["Inactive90Plus"].sum())
    ],
    [
        "High Monetary Score (4-5)",
        int(customers["HistoricallyHighValue"].sum())
    ],
    [
        "Recovery Candidates",
        int(customers["RecoveryCandidate"].sum())
    ],
    [
        "Priority Recovery Candidates",
        int(customers["PriorityRecoveryCandidate"].sum())
    ],
    [
        "Candidate Historical Recorded Value",
        customers.loc[
            customers["RecoveryCandidate"],
            "RecordedValue"
        ].sum()
    ],
    [
        "Candidate Historical Delivered Value",
        customers.loc[
            customers["RecoveryCandidate"],
            "HistoricalDeliveredValue"
        ].sum()
    ]
], columns=["Metric", "Value"])

# --------------------------------------------------
# 5. Segment opportunity breakdown
# --------------------------------------------------

segment_opportunity = (
    customers.groupby("StableSegment")
    .agg(
        Customers=("CustomerID", "count"),
        Inactive90Plus=("Inactive90Plus", "sum"),
        RecoveryCandidates=("RecoveryCandidate", "sum"),
        PriorityCandidates=("PriorityRecoveryCandidate", "sum"),
        HistoricalRecordedValue=("RecordedValue", "sum"),
        HistoricalDeliveredValue=("HistoricalDeliveredValue", "sum")
    )
    .reset_index()
)

segment_opportunity["CandidateRatePct"] = (
    segment_opportunity["RecoveryCandidates"]
    / segment_opportunity["Customers"] * 100
)

# --------------------------------------------------
# 6. Candidate ranking
# --------------------------------------------------

candidates = customers.loc[
    customers["RecoveryCandidate"]
].copy()

candidates["PriorityTier"] = np.where(
    candidates["PriorityRecoveryCandidate"],
    "Tier 1 - High Frequency and Value",
    "Tier 2 - High Value"
)

# Rank on historical delivered value, not
# assumed future recoverable revenue.

candidates = candidates.sort_values(
    [
        "PriorityRecoveryCandidate",
        "HistoricalDeliveredValue",
        "HistoricalOrderCount"
    ],
    ascending=[False, False, False]
)

candidates["CandidateRank"] = np.arange(
    1, len(candidates) + 1
)

# --------------------------------------------------
# 7. Validation
# --------------------------------------------------

assert customers["Orders"].sum() == 200000
assert customers["RecordedValue"].sum() == 164914494

assert (
    customers["HistoricalDeliveredValue"].sum()
    == 132092968
)

assert (
    customers["RecoveryCandidate"]
    <= customers["Inactive90Plus"]
).all()

assert (
    customers["PriorityRecoveryCandidate"]
    <= customers["RecoveryCandidate"]
).all()

assert segment_opportunity["Customers"].sum() == 20000

assert (
    segment_opportunity["RecoveryCandidates"].sum()
    == len(candidates)
)

# --------------------------------------------------
# 8. Export
# --------------------------------------------------

reports = {
    "customer_recovery_scorecard.csv": customers,
    "recovery_opportunity_summary.csv": candidate_summary,
    "recovery_by_rfm_segment.csv": segment_opportunity,
    "recovery_candidate_ranking.csv": candidates,
    "priority_recovery_candidates.csv": candidates.loc[
        candidates["PriorityRecoveryCandidate"]
    ]
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
print("FOODPULSE 360 | CUSTOMER RECOVERY PRIORITIZATION")
print("=" * 65)

print("\nRECOVERY SUMMARY")
print(candidate_summary.to_string(index=False))

print("\nSEGMENT OPPORTUNITY")
print(
    segment_opportunity.round(2).to_string(index=False)
)

print("\nTOP 10 CANDIDATES")
print(
    candidates[
        [
            "CustomerID",
            "StableSegment",
            "DaysSinceLastOrder",
            "HistoricalOrderCount",
            "HistoricalDeliveredValue",
            "PriorityTier"
        ]
    ].head(10).to_string(index=False)
)

print("\n[PASS] Customer and financial totals reconciled.")
print("[PASS] Candidate eligibility rules validated.")
print("[SUCCESS] 5 reports generated.")