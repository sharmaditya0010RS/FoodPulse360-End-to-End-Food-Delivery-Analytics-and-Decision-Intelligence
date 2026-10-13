from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
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
    RED,
)


st.set_page_config(
    page_title="FoodPulse 360 | Command Center",
    page_icon="🍽️",
    layout="wide",
    initial_sidebar_state="expanded"
)

inject_css()


@st.cache_data(ttl=300)
def get_data():
    kpis = query_data(
        "SELECT * FROM foodpulse.vw_executive_kpis"
    )

    monthly = query_data("""
        SELECT *
        FROM foodpulse.vw_monthly_performance
        ORDER BY order_month
    """)

    statuses = query_data("""
        SELECT *
        FROM foodpulse.vw_order_status
        ORDER BY orders DESC
    """)

    return kpis, monthly, statuses


def main():
    page_header(
        "Executive intelligence / Overview",
        "Command Center",
        "A unified view of marketplace performance, "
        "customer demand, operational exposure and decisions."
    )

    try:
        kpi_df, monthly, statuses = get_data()
    except Exception as exc:
        st.error("Unable to connect to PostgreSQL.")
        st.exception(exc)
        st.stop()

    k = kpi_df.iloc[0]

    monthly["order_month"] = pd.to_datetime(
        monthly["order_month"].to_numpy(),
        errors="raise"
    )

    numeric_cols = [
        "recorded_order_value",
        "delivered_order_value",
        "orders",
        "cancelled_orders",
        "cancellation_rate_pct",
    ]

    for col in numeric_cols:
        monthly[col] = pd.to_numeric(
            monthly[col],
            errors="raise"
        )

    # ---------------------------------------------
    # Executive KPIs
    # ---------------------------------------------

    st.subheader("Marketplace Pulse")

    c1, c2, c3, c4 = st.columns(4)

    c1.metric(
        "Recorded Order Value",
        format_inr(k["recorded_order_value"]),
        help="Recorded order face value, not platform revenue."
    )

    c2.metric(
        "Delivered-Order Value",
        format_inr(k["delivered_order_value"]),
        help="Face value of delivered-status orders."
    )

    c3.metric(
        "Total Orders",
        f"{int(k['total_orders']):,}"
    )

    c4.metric(
        "Cancellation Rate",
        f"{float(k['cancellation_rate_pct']):.2f}%"
    )

    c5, c6, c7, c8 = st.columns(4)

    c5.metric(
        "Customers",
        f"{int(k['active_customers']):,}"
    )

    c6.metric(
        "Active Restaurants",
        f"{int(k['active_restaurants']):,}"
    )

    c7.metric(
        "Average Order Value",
        f"₹{float(k['average_order_value']):,.0f}"
    )

    c8.metric(
        "Chronology Flags",
        f"{int(k['chronology_flagged_orders']):,}"
    )

    st.divider()

    # ---------------------------------------------
    # Period selection
    # ---------------------------------------------

    st.subheader("Performance Explorer")

    period_options = {
        "All periods": None,
        "2023": 2023,
        "2024": 2024,
        "2025 YTD": 2025
    }

    selected = st.segmented_control(
        "Analysis period",
        options=list(period_options),
        default="All periods"
    )

    selected_key = selected or "All periods"
    year = period_options.get(selected_key)

    filtered = monthly.copy()

    if year is not None:
        filtered = filtered.loc[
            filtered["order_month"].dt.year == year
        ]

    if filtered.empty:
        st.warning("No observations for this period.")
        st.stop()

    period_orders = int(filtered["orders"].sum())
    period_value = float(
        filtered["recorded_order_value"].sum()
    )

    st.caption(
        f"Selected period: {period_orders:,} orders · "
        f"{format_inr(period_value)} recorded order value"
    )

    # ---------------------------------------------
    # Charts
    # ---------------------------------------------

    left, right = st.columns([1.4, 1])

    with left:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=filtered["order_month"],
            y=filtered["recorded_order_value"],
            mode="lines+markers",
            name="Recorded value",
            line=dict(
                color=GREEN,
                width=3,
                shape="spline"
            ),
            marker=dict(size=6),
            fill="tozeroy",
            fillcolor="rgba(52,211,153,0.08)",
            hovertemplate=(
                "%{x|%b %Y}<br>"
                "₹%{y:,.0f}<extra></extra>"
            )
        ))

        fig.update_layout(
            title="Recorded Order Value",
            yaxis_title="Order value (₹)",
            xaxis_title=""
        )

        st.plotly_chart(
            style_chart(fig),
            use_container_width=True
        )

    with right:
        fig = go.Figure()

        fig.add_trace(go.Bar(
            x=filtered["order_month"],
            y=filtered["orders"],
            marker_color=BLUE,
            name="Orders",
            hovertemplate=(
                "%{x|%b %Y}<br>"
                "%{y:,} orders<extra></extra>"
            )
        ))

        fig.update_layout(
            title="Order Volume",
            yaxis_title="Orders",
            xaxis_title=""
        )

        st.plotly_chart(
            style_chart(fig),
            use_container_width=True
        )

    left, right = st.columns([1, 1])

    with left:
        fig = go.Figure()

        fig.add_trace(go.Scatter(
            x=filtered["order_month"],
            y=filtered["cancellation_rate_pct"],
            mode="lines+markers",
            line=dict(color=RED, width=3),
            marker=dict(size=6),
            name="Cancellation rate",
            hovertemplate=(
                "%{x|%b %Y}<br>"
                "%{y:.2f}%<extra></extra>"
            )
        ))

        fig.update_layout(
            title="Monthly Cancellation Rate",
            yaxis_title="Cancellation (%)"
        )

        st.plotly_chart(
            style_chart(fig),
            use_container_width=True
        )

    with right:
        colors = {
            "Delivered": GREEN,
            "Delayed": AMBER,
            "Cancelled": RED
        }

        fig = go.Figure(go.Pie(
            labels=statuses["order_status"],
            values=statuses["orders"],
            hole=0.68,
            marker=dict(
                colors=[
                    colors.get(str(s), BLUE)
                    for s in statuses["order_status"]
                ]
            ),
            textinfo="percent",
            hovertemplate=(
                "%{label}<br>"
                "%{value:,} orders<br>"
                "%{percent}<extra></extra>"
            )
        ))

        fig.update_layout(
            title="Overall Order Status Mix"
        )

        st.plotly_chart(
            style_chart(fig),
            use_container_width=True
        )

    st.caption(
        "Order status mix reflects the full dataset; "
        "the monthly charts follow the selected period."
    )

    st.divider()

    # ---------------------------------------------
    # Insight narrative
    # ---------------------------------------------

    st.subheader("Intelligence Brief")

    insight(
        "Growth signal requires period normalization",
        "September 2025 ends on the 26th. "
        "The validated September 1–26 versus August 1–26 "
        "comparison shows approximately 1.39% fewer orders. "
        "The estimated rate-ratio confidence interval "
        "includes no change, so a meaningful decline "
        "has not been established."
    )

    insight(
        "Cancellation exposure is operational, not profit loss",
        "19,947 orders are marked cancelled, representing "
        "₹1.64 Cr in recorded order face value. "
        "Refunds, commissions and settlement details "
        "are unavailable; this is not a proven loss."
    )

    insight(
        "Customer recovery is a testable opportunity",
        "2,431 historically high-value customers have "
        "been inactive for over 90 days, including "
        "1,939 Tier 1 screening candidates. "
        "These are outreach candidates, not predicted "
        "incremental conversions."
    )

    insight(
        "Restaurant risk findings require caution",
        "Individual restaurants have sparse order histories. "
        "The validated multiple-testing analysis found "
        "no statistically significant high-risk restaurants "
        "after false-discovery-rate adjustment."
    )

    st.divider()

    # ---------------------------------------------
    # Recommendations
    # ---------------------------------------------

    st.subheader("Executive Decision Queue")

    with st.container(border=True):
        st.markdown(
            "**Priority 01 · Validate recovery economics**"
        )
        st.write(
            "Run a consent-compliant randomized outreach pilot "
            "on eligible high-value inactive customers. "
            "Measure incremental orders and contribution "
            "against a holdout group."
        )

    with st.container(border=True):
        st.markdown(
            "**Priority 02 · Investigate cancellation causes**"
        )
        st.write(
            "Collect cancellation reasons, restaurant "
            "acceptance times, courier events and refunds "
            "before attributing exposure to specific causes."
        )

    with st.container(border=True):
        st.markdown(
            "**Priority 03 · Improve data trust**"
        )
        st.write(
            "Resolve signup chronology violations and "
            "scraped restaurant attribute contamination "
            "before deploying acquisition-cohort or "
            "restaurant-risk decision rules."
        )

    st.divider()

    st.caption(
        "FOODPULSE 360 / V2.0 · "
        "PostgreSQL-backed intelligence · "
        "Historical observations, not live marketplace activity"
    )


if __name__ == "__main__":
    main()