from pathlib import Path
import sys
import math

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.core.database import load_report
from dashboard.core.design import (
    inject_css,
    page_header,
    insight,
    style_chart,
    format_inr,
    GREEN,
    BLUE,
    AMBER,
    RED,
)

st.set_page_config(
    page_title="FoodPulse | Campaign Simulator",
    page_icon="🧮",
    layout="wide",
)

inject_css()

page_header(
    "Business decisions / Page 07",
    "Campaign Profit Simulator",
    "Try different campaign ideas before spending money. "
    "Change the assumptions to see possible outcomes."
)

st.warning(
    "This is a what-if calculator, NOT a prediction. "
    "No campaign results or actual profit data "
    "are available in the dataset."
)


@st.cache_data(show_spinner=False)
def get_candidates():
    df = load_report(
        "customer_recovery/recovery_candidate_ranking.csv"
    )

    required = [
        "CustomerID",
        "HistoricalDeliveredValue",
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(f"Missing fields: {missing}")

    df["HistoricalDeliveredValue"] = pd.to_numeric(
        df["HistoricalDeliveredValue"],
        errors="raise"
    )

    return df


try:
    candidates = get_candidates()
except Exception as exc:
    st.error("Could not load the customer recovery report.")
    st.exception(exc)
    st.stop()


# --------------------------------------------------
# Historical reference only
# --------------------------------------------------

candidate_count = len(candidates)

# Average historical delivered value per recorded
# delivered order is NOT a campaign basket estimate.
# Use observed delivered-order AOV from the warehouse.

from dashboard.core.database import query_data

aov_df = query_data("""
    SELECT
        AVG(order_value_clean) AS delivered_order_aov
    FROM foodpulse.fact_orders
    WHERE is_delivered = TRUE
""")

historical_aov = float(
    aov_df.iloc[0]["delivered_order_aov"]
)

st.subheader("Step 1 — Choose Your Campaign")

c1, c2 = st.columns(2)

with c1:
    target_customers = st.slider(
        "How many customers will receive the campaign?",
        min_value=100,
        max_value=candidate_count,
        value=candidate_count,
        step=1,
    )

    conversion_rate = st.slider(
        "Expected EXTRA customers who order (%)",
        min_value=0.0,
        max_value=20.0,
        value=5.0,
        step=0.5,
        help=(
            "Extra orders caused by the campaign, "
            "compared with doing nothing."
        )
    )

with c2:
    contribution_margin = st.slider(
        "Money left from each order before campaign costs (%)",
        min_value=0.0,
        max_value=40.0,
        value=15.0,
        step=1.0,
        help=(
            "Assumed contribution margin. "
            "This is NOT measured from our dataset."
        )
    )

    cost_per_customer = st.slider(
        "Campaign cost per customer (₹)",
        min_value=0,
        max_value=100,
        value=10,
        step=1,
        help=(
            "Assumed average campaign cost for "
            "every customer targeted."
        )
    )

st.divider()

st.subheader("Step 2 — Set the Expected Order Amount")

order_value = st.number_input(
    "Expected value of one additional order (₹)",
    min_value=100.0,
    max_value=5000.0,
    value=round(historical_aov, 2),
    step=25.0,
)

st.caption(
    f"The starting value of ₹{historical_aov:,.2f} "
    "comes from the average historical delivered order. "
    "You can change it."
)

# --------------------------------------------------
# Calculations
# --------------------------------------------------

rate = conversion_rate / 100
margin = contribution_margin / 100

expected_extra_orders = target_customers * rate

expected_extra_order_value = (
    expected_extra_orders * order_value
)

expected_contribution = (
    expected_extra_order_value * margin
)

campaign_cost = (
    target_customers * cost_per_customer
)

estimated_net = (
    expected_contribution - campaign_cost
)

contribution_per_extra_order = (
    order_value * margin
)

if contribution_per_extra_order > 0:
    break_even_rate = (
        cost_per_customer
        / contribution_per_extra_order
        * 100
    )
else:
    break_even_rate = math.inf

# --------------------------------------------------
# Results
# --------------------------------------------------

st.subheader("Step 3 — See the Possible Result")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Expected Extra Orders",
    f"{expected_extra_orders:,.1f}"
)

c2.metric(
    "Extra Order Value",
    format_inr(expected_extra_order_value)
)

c3.metric(
    "Campaign Cost",
    format_inr(campaign_cost)
)

c4.metric(
    "Estimated Net Contribution",
    format_inr(estimated_net),
    delta=(
        "Positive scenario"
        if estimated_net > 0
        else "Negative scenario"
        if estimated_net < 0
        else "Break-even"
    ),
    delta_color=(
        "normal"
        if estimated_net >= 0
        else "inverse"
    )
)

st.caption(
    "Extra orders are expected values, not actual "
    "whole-number orders. All results depend "
    "on the assumptions above."
)

if estimated_net > 0:
    st.success(
        "Under your assumptions, the campaign "
        "would produce positive net contribution."
    )
elif estimated_net < 0:
    st.error(
        "Under your assumptions, the campaign "
        "would cost more than the extra contribution."
    )
else:
    st.info(
        "Under your assumptions, the campaign "
        "would approximately break even."
    )

st.divider()

# --------------------------------------------------
# Break-even
# --------------------------------------------------

st.subheader("How Many Extra Customers Must Order?")

if math.isfinite(break_even_rate):
    st.metric(
        "Minimum Extra Conversion Needed",
        f"{break_even_rate:.2f}%"
    )

    if break_even_rate > 100:
        st.warning(
            "Break-even would require more than "
            "100% of targeted customers to place "
            "an extra order. This scenario cannot "
            "break even under the one-order assumption."
        )
else:
    st.warning(
        "Break-even cannot be calculated because "
        "the assumed contribution per order is zero."
    )

# --------------------------------------------------
# Scenario curve
# --------------------------------------------------

st.subheader("What Happens if More Customers Respond?")

rates = [x / 2 for x in range(0, 41)]

results = [
    target_customers
    * (r / 100)
    * order_value
    * margin
    - campaign_cost
    for r in rates
]

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=rates,
    y=results,
    mode="lines",
    line=dict(color=GREEN, width=4),
    fill="tozeroy",
    fillcolor="rgba(52,211,153,0.08)",
    name="Estimated net contribution",
))

fig.add_hline(
    y=0,
    line_dash="dash",
    line_color=AMBER,
    annotation_text="Break-even line"
)

fig.add_vline(
    x=conversion_rate,
    line_dash="dot",
    line_color=BLUE,
    annotation_text="Your assumption"
)

fig.update_layout(
    title="Possible Campaign Outcome by Extra Conversion Rate",
    xaxis_title="Extra customers who order (%)",
    yaxis_title="Estimated net contribution (₹)"
)

st.plotly_chart(
    style_chart(fig, height=460),
    use_container_width=True
)

# --------------------------------------------------
# Plain English insights
# --------------------------------------------------

st.divider()
st.subheader("What Does This Mean?")

insight(
    "Campaign success depends on extra orders",
    "The campaign only creates additional value "
    "if customers place orders they would not "
    "have placed without the campaign."
)

insight(
    "Discounts and marketing costs matter",
    "A campaign can increase orders and still "
    "lose money if the cost of reaching customers "
    "is greater than the extra contribution."
)

insight(
    "Test your assumptions with real customers",
    "Use a small randomized campaign with a "
    "comparison group before committing "
    "to a large budget."
)

st.subheader("Recommended Next Steps")

with st.container(border=True):
    st.markdown("**1. Run a small pilot**")
    st.write(
        "Start with eligible high-priority customers "
        "rather than contacting everyone."
    )

with st.container(border=True):
    st.markdown("**2. Measure additional orders fairly**")
    st.write(
        "Compare customers who received the campaign "
        "with similar customers who did not."
    )

with st.container(border=True):
    st.markdown("**3. Update the simulator with real costs**")
    st.write(
        "Replace assumed margins and campaign costs "
        "with actual business financial data."
    )

st.caption(
    "Simulation only. No guaranteed results. "
    "One incremental order per converted customer "
    "is assumed for this model."
)