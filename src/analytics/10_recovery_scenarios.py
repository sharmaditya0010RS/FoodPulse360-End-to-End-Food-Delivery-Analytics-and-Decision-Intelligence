from pathlib import Path
import itertools
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = (
    ROOT / "data/reports/customer_recovery"
    / "recovery_candidate_ranking.csv"
)
OUTPUT = ROOT / "data/reports/recovery_scenarios"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_csv(SOURCE)

assert len(df) == 2431
assert df["CustomerID"].is_unique

# --------------------------------------------------
# 1. Historical AOV for scenario sizing
# --------------------------------------------------

historical_orders = df["HistoricalOrderCount"].sum()
historical_delivered_value = (
    df["HistoricalDeliveredValue"].sum()
)

historical_delivered_value_per_order = (
    historical_delivered_value / historical_orders
)

# Hypothetical inputs, NOT observed outcomes:
# - Incremental conversion = additional customers
#   placing one order because of the campaign.
# - Contribution margin = platform contribution
#   before campaign incentive/contact costs.
# - Incentive paid to every targeted customer
#   is deliberately conservative.

conversion_rates = [0.01, 0.03, 0.05, 0.10]
contribution_margins = [0.10, 0.15, 0.20]
incentives_per_target = [0, 5, 10, 20]

target_count = len(df)

scenarios = []

for conversion, margin, incentive in itertools.product(
    conversion_rates,
    contribution_margins,
    incentives_per_target
):
    incremental_orders = target_count * conversion

    incremental_order_value = (
        incremental_orders
        * historical_delivered_value_per_order
    )

    contribution_before_campaign_cost = (
        incremental_order_value * margin
    )

    campaign_cost = target_count * incentive

    net_contribution = (
        contribution_before_campaign_cost - campaign_cost
    )

    break_even_conversion = (
        campaign_cost
        / (
            target_count
            * historical_delivered_value_per_order
            * margin
        )
        if margin > 0 else float("nan")
    )

    scenarios.append({
        "TargetCustomers": target_count,
        "IncrementalConversionAssumption": conversion,
        "ContributionMarginAssumption": margin,
        "IncentivePerTarget": incentive,
        "HistoricalDeliveredValuePerOrderProxy":
            historical_delivered_value_per_order,
        "HypotheticalIncrementalOrders": incremental_orders,
        "HypotheticalIncrementalOrderValue":
            incremental_order_value,
        "HypotheticalContributionBeforeCost":
            contribution_before_campaign_cost,
        "HypotheticalCampaignCost": campaign_cost,
        "HypotheticalNetContribution": net_contribution,
        "BreakEvenIncrementalConversion":
            break_even_conversion
    })

scenarios = pd.DataFrame(scenarios)

# --------------------------------------------------
# 2. Tier-level scenario sizing
# --------------------------------------------------

tier_summary = (
    df.groupby("PriorityTier")
    .agg(
        Customers=("CustomerID", "count"),
        HistoricalOrders=("HistoricalOrderCount", "sum"),
        HistoricalDeliveredValue=(
            "HistoricalDeliveredValue", "sum"
        )
    )
    .reset_index()
)

tier_summary["HistoricalDeliveredValuePerOrder"] = (
    tier_summary["HistoricalDeliveredValue"]
    / tier_summary["HistoricalOrders"]
)

# --------------------------------------------------
# 3. Break-even reference table
# --------------------------------------------------

break_even = (
    scenarios.loc[
        scenarios["IncrementalConversionAssumption"] == 0.03,
        [
            "ContributionMarginAssumption",
            "IncentivePerTarget",
            "BreakEvenIncrementalConversion"
        ]
    ]
    .drop_duplicates()
    .sort_values(
        [
            "ContributionMarginAssumption",
            "IncentivePerTarget"
        ]
    )
)

break_even["BreakEvenConversionPct"] = (
    break_even["BreakEvenIncrementalConversion"] * 100
)

# --------------------------------------------------
# 4. Validation
# --------------------------------------------------

assert target_count == 2431
assert tier_summary["Customers"].sum() == target_count
assert historical_delivered_value == 21076712
assert len(scenarios) == 48

assert (
    scenarios["HypotheticalIncrementalOrders"] >= 0
).all()

assert (
    scenarios["HypotheticalCampaignCost"] >= 0
).all()

assert (
    (
        scenarios["HypotheticalContributionBeforeCost"]
        - scenarios["HypotheticalCampaignCost"]
        - scenarios["HypotheticalNetContribution"]
    ).abs() < 1e-6
).all()

# --------------------------------------------------
# 5. Export
# --------------------------------------------------

reports = {
    "recovery_scenario_grid.csv": scenarios,
    "recovery_tier_summary.csv": tier_summary,
    "break_even_reference.csv": break_even
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | RECOVERY SCENARIO SIMULATOR")
print("=" * 65)

print("\nTIER SUMMARY")
print(tier_summary.round(2).to_string(index=False))

print("\nBREAK-EVEN REFERENCE")
print(
    break_even[
        [
            "ContributionMarginAssumption",
            "IncentivePerTarget",
            "BreakEvenConversionPct"
        ]
    ].round(2).to_string(index=False)
)

print("\nEXAMPLE SCENARIOS")
print(
    scenarios.loc[
        (scenarios["ContributionMarginAssumption"] == 0.15)
        & (scenarios["IncentivePerTarget"] == 10),
        [
            "IncrementalConversionAssumption",
            "HypotheticalIncrementalOrderValue",
            "HypotheticalCampaignCost",
            "HypotheticalNetContribution"
        ]
    ].round(2).to_string(index=False)
)

print("\n[PASS] Candidate and historical value totals reconciled.")
print("[PASS] Scenario accounting identities validated.")
print("[SUCCESS] 3 scenario reports generated.")