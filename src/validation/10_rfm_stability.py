from pathlib import Path
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/reports/customer_rfm/customer_rfm_scorecard.csv"
OUTPUT = ROOT / "data/reports/rfm_stability"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(SOURCE)

assert len(df) == 20000
assert df["CustomerID"].is_unique

# --------------------------------------------------
# 1. Audit original score consistency
# --------------------------------------------------

def score_consistency(data, metric, score):
    grouped = (
        data.groupby(metric)[score]
        .agg(["min", "max", "count"])
        .reset_index()
    )

    inconsistent = grouped.loc[
        grouped["min"] != grouped["max"]
    ].copy()

    return grouped, inconsistent


recency_audit, recency_inconsistent = score_consistency(
    df, "RecencyDays", "RScore"
)

frequency_audit, frequency_inconsistent = score_consistency(
    df, "Frequency", "FScore"
)

monetary_audit, monetary_inconsistent = score_consistency(
    df, "RecordedMonetary", "MScore"
)

# --------------------------------------------------
# 2. Tie-consistent percentile scores
# --------------------------------------------------

def stable_score(series, higher_is_better=True):
    # Average rank gives identical values identical ranks.
    percentile = series.rank(
        method="average",
        pct=True,
        ascending=True
    )

    if not higher_is_better:
        percentile = 1 - percentile

    scores = np.ceil(percentile * 5)

    return (
        pd.Series(scores, index=series.index)
        .clip(1, 5)
        .astype(int)
    )


df["RScoreStable"] = stable_score(
    df["RecencyDays"],
    higher_is_better=False
)

df["FScoreStable"] = stable_score(
    df["Frequency"],
    higher_is_better=True
)

df["MScoreStable"] = stable_score(
    df["RecordedMonetary"],
    higher_is_better=True
)

# --------------------------------------------------
# 3. Rebuild segments using stable scores
# --------------------------------------------------

r = df["RScoreStable"]
f = df["FScoreStable"]
m = df["MScoreStable"]

conditions = [
    (r >= 4) & (f >= 4) & (m >= 4),
    (r <= 2) & (f >= 4),
    (r >= 4) & (f <= 2),
    (r <= 2) & (f <= 2),
    (f >= 4) & (m >= 4)
]

labels = [
    "Champions",
    "At Risk",
    "Promising Occasional",
    "Low Engagement",
    "High Value Regulars"
]

df["StableSegment"] = np.select(
    conditions,
    labels,
    default="Core Customers"
)

df["SegmentChanged"] = (
    df["Segment"] != df["StableSegment"]
)

# --------------------------------------------------
# 4. Stable segment summary
# --------------------------------------------------

segments = (
    df.groupby("StableSegment")
    .agg(
        Customers=("CustomerID", "count"),
        Orders=("Frequency", "sum"),
        RecordedValue=("RecordedMonetary", "sum"),
        DeliveredValue=("DeliveredMonetary", "sum"),
        MedianRecency=("RecencyDays", "median")
    )
    .reset_index()
)

segments["CustomerSharePct"] = (
    segments["Customers"] / len(df) * 100
)

segments["RecordedValueSharePct"] = (
    segments["RecordedValue"]
    / df["RecordedMonetary"].sum() * 100
)

# --------------------------------------------------
# 5. Summary
# --------------------------------------------------

summary = pd.DataFrame([
    ["Total Customers", len(df)],
    ["Distinct Recency Values", df["RecencyDays"].nunique()],
    ["Distinct Frequency Values", df["Frequency"].nunique()],
    ["Distinct Monetary Values",
     df["RecordedMonetary"].nunique()],
    ["Original Recency Tie Inconsistencies",
     len(recency_inconsistent)],
    ["Original Frequency Tie Inconsistencies",
     len(frequency_inconsistent)],
    ["Original Monetary Tie Inconsistencies",
     len(monetary_inconsistent)],
    ["Customers With Changed R Score",
     int((df["RScore"] != df["RScoreStable"]).sum())],
    ["Customers With Changed F Score",
     int((df["FScore"] != df["FScoreStable"]).sum())],
    ["Customers With Changed M Score",
     int((df["MScore"] != df["MScoreStable"]).sum())],
    ["Customers With Changed Segment",
     int(df["SegmentChanged"].sum())]
], columns=["Metric", "Value"])

# --------------------------------------------------
# 6. Independent validation
# --------------------------------------------------

assert segments["Customers"].sum() == 20000
assert segments["Orders"].sum() == 200000
assert segments["RecordedValue"].sum() == 164914494
assert segments["DeliveredValue"].sum() == 132092968

for metric, score in [
    ("RecencyDays", "RScoreStable"),
    ("Frequency", "FScoreStable"),
    ("RecordedMonetary", "MScoreStable")
]:
    assert (
        df.groupby(metric)[score].nunique().max() == 1
    ), f"Tie inconsistency detected: {metric}"

assert df["RScoreStable"].between(1, 5).all()
assert df["FScoreStable"].between(1, 5).all()
assert df["MScoreStable"].between(1, 5).all()

# --------------------------------------------------
# 7. Export
# --------------------------------------------------

reports = {
    "rfm_scoring_audit.csv": summary,
    "stable_customer_rfm.csv": df,
    "stable_segment_summary.csv": segments,
    "original_recency_tie_issues.csv": recency_inconsistent,
    "original_frequency_tie_issues.csv": frequency_inconsistent,
    "original_monetary_tie_issues.csv": monetary_inconsistent
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | RFM STABILITY VALIDATION")
print("=" * 65)

print("\nSCORING AUDIT")
print(summary.to_string(index=False))

print("\nSTABLE SEGMENTS")
print(segments.round(2).to_string(index=False))

print("\n[PASS] Same metric values receive same scores.")
print("[PASS] Customer, order and financial totals reconciled.")
print("[SUCCESS] 6 reports generated.")