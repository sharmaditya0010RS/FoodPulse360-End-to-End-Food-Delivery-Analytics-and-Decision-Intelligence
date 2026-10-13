from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from dashboard.core.database import query_data
from dashboard.core.design import (
    inject_css,
    page_header,
    insight,
    style_chart,
    format_inr,
    GREEN,
    BLUE,
    AMBER,
)

# ==========================================================
# PAGE SETTINGS
# ==========================================================

st.set_page_config(
    page_title="FoodPulse | Revenue & Growth",
    page_icon="📈",
    layout="wide",
)

inject_css()

page_header(
    "Business performance / Page 01",
    "Revenue & Growth Intelligence",
    "Understand how many orders customers place, "
    "how much those orders are worth, and whether "
    "the business is growing."
)

st.info(
    "Order value means the amount recorded on customer "
    "orders. It is not the company's actual revenue or profit."
)


# ==========================================================
# LOAD DATA
# ==========================================================

@st.cache_data(ttl=300, show_spinner=False)
def load_monthly_data():
    return query_data("""
        SELECT
            order_month,
            orders,
            active_customers,
            active_restaurants,
            recorded_order_value,
            delivered_order_value,
            average_order_value,
            cancelled_orders,
            cancellation_rate_pct
        FROM foodpulse.vw_monthly_performance
        ORDER BY order_month
    """)


try:
    monthly = load_monthly_data()
except Exception as exc:
    st.error("Unable to load monthly performance data.")
    st.exception(exc)
    st.stop()


monthly["order_month"] = pd.to_datetime(
    monthly["order_month"]
)

numeric_columns = [
    "orders",
    "active_customers",
    "active_restaurants",
    "recorded_order_value",
    "delivered_order_value",
    "average_order_value",
    "cancelled_orders",
    "cancellation_rate_pct",
]

for col in numeric_columns:
    monthly[col] = pd.to_numeric(
        monthly[col],
        errors="raise"
    )

monthly["Year"] = monthly["order_month"].dt.year
monthly["Month"] = monthly["order_month"].dt.month
monthly["MonthName"] = monthly[
    "order_month"
].dt.strftime("%b %Y")


# ==========================================================
# FILTERS
# ==========================================================

st.subheader("Choose Your Time Period")

available_years = sorted(
    monthly["Year"].unique().tolist()
)

selected_years = st.multiselect(
    "Select years to explore",
    options=available_years,
    default=available_years,
)

if not selected_years:
    st.warning("Please select at least one year.")
    st.stop()

filtered = monthly.loc[
    monthly["Year"].isin(selected_years)
].copy()

filtered = filtered.sort_values("order_month")


# ==========================================================
# MAIN KPIs
# ==========================================================

st.subheader("Business Overview")

total_orders = int(filtered["orders"].sum())

recorded_value = float(
    filtered["recorded_order_value"].sum()
)

delivered_value = float(
    filtered["delivered_order_value"].sum()
)

cancelled_orders = int(
    filtered["cancelled_orders"].sum()
)

average_order_value = (
    recorded_value / total_orders
    if total_orders > 0 else 0
)

cancellation_rate = (
    cancelled_orders / total_orders * 100
    if total_orders > 0 else 0
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Orders",
    f"{total_orders:,}"
)

c2.metric(
    "Total Order Value",
    format_inr(recorded_value)
)

c3.metric(
    "Delivered Order Value",
    format_inr(delivered_value)
)

c4.metric(
    "Average Order Value",
    f"₹{average_order_value:,.2f}"
)

c5, c6 = st.columns(2)

c5.metric(
    "Cancelled Orders",
    f"{cancelled_orders:,}"
)

c6.metric(
    "Cancellation Rate",
    f"{cancellation_rate:.2f}%"
)

st.divider()


# ==========================================================
# MONTHLY ORDER TREND
# ==========================================================

st.subheader("How Is the Business Performing Each Month?")

left, right = st.columns(2)

with left:

    fig = go.Figure()

    fig.add_trace(
        go.Scatter(
            x=filtered["order_month"],
            y=filtered["orders"],
            mode="lines+markers",
            line=dict(
                color=BLUE,
                width=3
            ),
            marker=dict(size=7),
            fill="tozeroy",
            fillcolor="rgba(96,165,250,0.10)",
            hovertemplate=(
                "%{x|%b %Y}<br>"
                "%{y:,} orders<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title="Orders Received Each Month",
        xaxis_title="",
        yaxis_title="Number of orders"
    )

    st.plotly_chart(
        style_chart(fig),
        use_container_width=True
    )


with right:

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=filtered["order_month"],
            y=filtered["recorded_order_value"],
            marker_color=GREEN,
            hovertemplate=(
                "%{x|%b %Y}<br>"
                "₹%{y:,.0f}<extra></extra>"
            )
        )
    )

    fig.update_layout(
        title="Total Order Value Each Month",
        xaxis_title="",
        yaxis_title="Order value (₹)"
    )

    st.plotly_chart(
        style_chart(fig),
        use_container_width=True
    )


# ==========================================================
# MONTHLY GROWTH
# ==========================================================

st.divider()

st.subheader("Are Orders Increasing or Decreasing?")

# Calculate growth on the complete monthly sequence
# before applying year filters.

monthly["OrderGrowthPct"] = (
    monthly["orders"].pct_change() * 100
)

growth = monthly.loc[
    monthly["Year"].isin(selected_years)
].copy()

# The final month is incomplete.
latest_date = pd.Timestamp("2025-09-26")

growth["IsIncompleteMonth"] = (
    growth["order_month"].dt.to_period("M")
    == latest_date.to_period("M")
)

growth_valid = growth.loc[
    ~growth["IsIncompleteMonth"]
].dropna(subset=["OrderGrowthPct"])

fig = go.Figure()

fig.add_trace(
    go.Bar(
        x=growth_valid["order_month"],
        y=growth_valid["OrderGrowthPct"],
        marker_color=[
            GREEN if x >= 0 else AMBER
            for x in growth_valid["OrderGrowthPct"]
        ],
        hovertemplate=(
            "%{x|%b %Y}<br>"
            "%{y:+.2f}% change<extra></extra>"
        )
    )
)

fig.add_hline(
    y=0,
    line_dash="dash",
    line_color="#94A3B8"
)

fig.update_layout(
    title="Change in Orders Compared with Previous Month",
    xaxis_title="",
    yaxis_title="Monthly change (%)"
)

st.plotly_chart(
    style_chart(fig, height=430),
    use_container_width=True
)

st.caption(
    "Green means more orders than the previous month. "
    "Yellow means fewer orders. September 2025 is "
    "excluded because its data is incomplete."
)


# ==========================================================
# YEARLY COMPARISON
# ==========================================================

st.divider()

st.subheader("Compare Business Performance by Year")

yearly = (
    monthly.groupby("Year", as_index=False)
    .agg(
        Orders=("orders", "sum"),
        OrderValue=("recorded_order_value", "sum"),
        DeliveredValue=("delivered_order_value", "sum"),
    )
)

yearly["OrderGrowthPct"] = (
    yearly["Orders"].pct_change() * 100
)

yearly["ValueGrowthPct"] = (
    yearly["OrderValue"].pct_change() * 100
)

yearly["Period"] = yearly["Year"].astype(str)

yearly.loc[
    yearly["Year"] == 2025,
    "Period"
] = "2025 (Jan–Sep 26)"

st.warning(
    "2025 contains only January 1 to September 26. "
    "Do not compare its total directly with full-year "
    "2023 or 2024 totals."
)

display_yearly = yearly[
    [
        "Period",
        "Orders",
        "OrderValue",
        "DeliveredValue",
    ]
].copy()

display_yearly.columns = [
    "Year",
    "Orders",
    "Total Order Value (₹)",
    "Delivered Order Value (₹)",
]

st.dataframe(
    display_yearly,
    use_container_width=True,
    hide_index=True
)


# ==========================================================
# BEST MONTH
# ==========================================================

st.divider()

st.subheader("Which Month Performed Best?")

complete_months = filtered.loc[
    filtered["order_month"].dt.to_period("M")
    < latest_date.to_period("M")
].copy()

if not complete_months.empty:

    best_orders = complete_months.iloc[
        complete_months["orders"].argmax()
    ]

    best_value = complete_months.iloc[
        complete_months["recorded_order_value"].argmax()
    ]

    c1, c2 = st.columns(2)

    c1.metric(
        "Month with Most Orders",
        best_orders["MonthName"]
    )

    c1.caption(
        f"{int(best_orders['orders']):,} orders"
    )

    c2.metric(
        "Month with Highest Order Value",
        best_value["MonthName"]
    )

    c2.caption(
        format_inr(
            best_value["recorded_order_value"]
        )
    )


# ==========================================================
# INSIGHTS
# ==========================================================

st.divider()

st.subheader("What Did We Learn?")

insight(
    "The latest month is incomplete",
    "Our records stop on September 26, 2025. "
    "Comparing this with all 31 days of August "
    "would make September look weaker than it "
    "really is."
)

insight(
    "A fair comparison shows a small difference",
    "Comparing September 1–26 with August 1–26, "
    "orders were about 1.39% lower. "
    "This difference could be normal variation, "
    "so we cannot confidently say demand declined."
)

insight(
    "Order value is not business profit",
    "Higher order value is useful, but we still "
    "need commission, refund and cost information "
    "to understand actual business earnings."
)


# ==========================================================
# RECOMMENDATIONS
# ==========================================================

st.divider()

st.subheader("What Should the Business Do?")

with st.container(border=True):
    st.markdown(
        "**1. Compare the same number of days**"
    )
    st.write(
        "For an incomplete month, compare the "
        "same dates from the previous month."
    )

with st.container(border=True):
    st.markdown(
        "**2. Track orders and order value together**"
    )
    st.write(
        "More orders do not always mean more "
        "money earned by the company."
    )

with st.container(border=True):
    st.markdown(
        "**3. Add real revenue information**"
    )
    st.write(
        "Collect commission, discounts, refunds "
        "and operating costs to calculate "
        "actual revenue and profit."
    )

st.divider()

st.caption(
    "FoodPulse 360 V2.0 | "
    "PostgreSQL-backed Revenue & Growth Intelligence"
)