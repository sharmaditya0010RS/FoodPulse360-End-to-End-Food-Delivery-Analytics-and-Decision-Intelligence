from pathlib import Path
import numpy as np
import pandas as pd
from scipy.stats import beta
from scipy.stats import binomtest

ROOT = Path(__file__).resolve().parents[2]

SOURCE = (
    ROOT / "data/reports/restaurant_performance"
    / "restaurant_scorecard.csv"
)

OUTPUT = ROOT / "data/reports/restaurant_risk"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(SOURCE)

# --------------------------------------------------
# 1. Validate restaurant scorecard
# --------------------------------------------------

assert len(df) == 54600
assert df["RestaurantID"].is_unique
assert df["Orders"].sum() == 200000
assert df["CancelledOrders"].sum() == 19947

df["QualityFlag"] = (
    df["QualityFlag"]
    .astype("string")
    .str.lower()
    .eq("true")
    .fillna(True)
)

# Exclude contaminated restaurant attributes
eligible = df.loc[~df["QualityFlag"]].copy()

assert len(eligible) == 50229
assert eligible["Orders"].sum() == 184141
assert eligible["CancelledOrders"].sum() == 18388

# --------------------------------------------------
# 2. Establish eligible-population baseline
# --------------------------------------------------

baseline = (
    eligible["CancelledOrders"].sum()
    / eligible["Orders"].sum()
)

# Empirical-Bayes-style smoothing with a fixed
# prior equivalent to 50 orders.
#
# Prior mean = eligible-population cancellation rate.
# Prior strength is an explicit modeling assumption.

prior_strength = 50

alpha_prior = baseline * prior_strength
beta_prior = (1 - baseline) * prior_strength

eligible["RawCancellationRate"] = (
    eligible["CancelledOrders"] / eligible["Orders"]
)

eligible["PosteriorAlpha"] = (
    eligible["CancelledOrders"] + alpha_prior
)

eligible["PosteriorBeta"] = (
    eligible["Orders"]
    - eligible["CancelledOrders"]
    + beta_prior
)

eligible["SmoothedCancellationRate"] = (
    eligible["PosteriorAlpha"]
    / (
        eligible["PosteriorAlpha"]
        + eligible["PosteriorBeta"]
    )
)

eligible["PosteriorProbAboveBaseline"] = (
    beta.sf(
        baseline,
        eligible["PosteriorAlpha"],
        eligible["PosteriorBeta"]
    )
)

# --------------------------------------------------
# 3. Candidate screening
# --------------------------------------------------

# Exploratory minimum-volume threshold.
# Not enough by itself to establish poor performance.

candidates = eligible.loc[
    eligible["Orders"] >= 10
].copy()

candidates["RawCancellationRatePct"] = (
    candidates["RawCancellationRate"] * 100
)

candidates["SmoothedCancellationRatePct"] = (
    candidates["SmoothedCancellationRate"] * 100
)

candidates["BaselineCancellationRatePct"] = (
    baseline * 100
)

# Exact one-sided binomial p-values.
# Null: cancellation probability equals baseline.
# Alternative: restaurant probability > baseline.

candidates["PValue"] = [
    binomtest(
        int(cancelled),
        int(orders),
        p=baseline,
        alternative="greater"
    ).pvalue
    for cancelled, orders in zip(
        candidates["CancelledOrders"],
        candidates["Orders"]
    )
]

# --------------------------------------------------
# 4. Benjamini-Hochberg multiple-test correction
# --------------------------------------------------

candidates = candidates.sort_values(
    "PValue"
).reset_index(drop=True)

m = len(candidates)

candidates["TestRank"] = np.arange(1, m + 1)

raw_q = (
    candidates["PValue"] * m
    / candidates["TestRank"]
)

candidates["AdjustedQValue"] = (
    np.minimum.accumulate(
        raw_q.to_numpy()[::-1]
    )[::-1]
).clip(0, 1)

candidates["StatisticallyFlagged"] = (
    candidates["AdjustedQValue"] < 0.05
)

# Separate exploratory monitoring label
candidates["MonitoringCandidate"] = (
    (candidates["PosteriorProbAboveBaseline"] >= 0.80)
    & (candidates["RawCancellationRate"] > baseline)
)

# --------------------------------------------------
# 5. Summaries
# --------------------------------------------------

summary = pd.DataFrame([
    ["Eligible Restaurants", len(eligible)],
    ["Eligible Orders", eligible["Orders"].sum()],
    ["Eligible Cancelled Orders",
     eligible["CancelledOrders"].sum()],
    ["Baseline Cancellation Rate Pct", baseline * 100],
    ["Prior Equivalent Orders", prior_strength],
    ["Restaurants With 10+ Orders", m],
    ["Exploratory Monitoring Candidates",
     int(candidates["MonitoringCandidate"].sum())],
    ["FDR-Significant Restaurants",
     int(candidates["StatisticallyFlagged"].sum())],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 6. Validation
# --------------------------------------------------

assert len(candidates) == 194

assert candidates["PValue"].between(0, 1).all()
assert candidates["AdjustedQValue"].between(0, 1).all()

assert (
    candidates["SmoothedCancellationRate"]
    .between(0, 1).all()
)

assert (
    candidates["PosteriorProbAboveBaseline"]
    .between(0, 1).all()
)

assert (
    candidates["AdjustedQValue"].diff()
    .fillna(0).ge(-1e-12).all()
)

# --------------------------------------------------
# 7. Export
# --------------------------------------------------

eligible.to_csv(
    OUTPUT / "restaurant_smoothed_scorecard.csv",
    index=False,
    encoding="utf-8-sig"
)

candidates.to_csv(
    OUTPUT / "restaurant_risk_candidates.csv",
    index=False,
    encoding="utf-8-sig"
)

candidates.loc[
    candidates["MonitoringCandidate"]
].to_csv(
    OUTPUT / "exploratory_monitoring_list.csv",
    index=False,
    encoding="utf-8-sig"
)

candidates.loc[
    candidates["StatisticallyFlagged"]
].to_csv(
    OUTPUT / "statistically_flagged_restaurants.csv",
    index=False,
    encoding="utf-8-sig"
)

summary.to_csv(
    OUTPUT / "risk_screening_summary.csv",
    index=False,
    encoding="utf-8-sig"
)

# --------------------------------------------------
# 8. Console output
# --------------------------------------------------

print("=" * 65)
print("FOODPULSE 360 | RESTAURANT RISK SCREENING")
print("=" * 65)

print("\nSCREENING SUMMARY")
print(summary.round(4).to_string(index=False))

print("\nTOP 10 CANDIDATES BY RAW P-VALUE")

columns = [
    "RestaurantID",
    "RestaurantName",
    "Orders",
    "CancelledOrders",
    "RawCancellationRatePct",
    "SmoothedCancellationRatePct",
    "PosteriorProbAboveBaseline",
    "PValue",
    "AdjustedQValue",
    "StatisticallyFlagged"
]

print(
    candidates[columns]
    .head(10)
    .round(4)
    .to_string(index=False)
)

print("\n[PASS] Eligible population reconciled.")
print("[PASS] Probability and adjusted p-value checks passed.")
print("[SUCCESS] 5 screening reports generated.")