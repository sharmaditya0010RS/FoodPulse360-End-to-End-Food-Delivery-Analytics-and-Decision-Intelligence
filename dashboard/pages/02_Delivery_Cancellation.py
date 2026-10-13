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
    RED,
)

st.set_page_config(
    page_title="FoodPulse | Delivery & Cancellation",
    page_icon="🚚",
    layout="wide",
)

inject_css()

page_header(
    "Operations / Page 02",
    "Delivery & Cancellation",
    "Understand which orders were completed, "
    "delayed or cancelled."
)

# -------------------------------------------------
# 1. Load data
# -------------------------------------------------

status = query_data("""
    SELECT *
    FROM foodpulse.vw_order_status
    ORDER BY orders DESC
""")

monthly = query_data("""
    SELECT
        order_month,
        orders,
        cancelled_orders,
        cancellation_rate_pct
    FROM foodpulse.vw_monthly_performance
    ORDER BY order_month
""")

for col in [
    "orders",
    "recorded_order_value",
    "delivered_order_value",
]:
    status[col] = pd.to_numeric(status[col])

monthly["order_month"] = pd.to_datetime(
    monthly["order_month"]
)

monthly["orders"] = pd.to_numeric(
    monthly["orders"]
)

monthly["cancelled_orders"] = pd.to_numeric(
    monthly["cancelled_orders"]
)

monthly["cancellation_rate_pct"] = pd.to_numeric(
    monthly["cancellation_rate_pct"]
)

# -------------------------------------------------
# 2. Filters
# -------------------------------------------------

st.subheader("Explore order performance")

selected_year = st.selectbox(
    "Select year",
    ["All years", 2023, 2024, 2025]
)

if selected_year == "All years":
    year_filter = ""
else:
    year_filter = (
        f"WHERE EXTRACT(YEAR FROM order_date) "
        f"= {int(selected_year)}"
    )

# This is a controlled dropdown, not free-form SQL.

filtered_status = query_data(f"""
    SELECT
        "order_status_clean" AS order_status,
        COUNT(*) AS orders,
        SUM("recorded_order_value")
            AS recorded_order_value
    FROM foodpulse.fact_orders
    {year_filter}
    GROUP BY "order_status_clean"
    ORDER BY orders DESC
""")

filtered_status["orders"] = pd.to_numeric(
    filtered_status["orders"]
)

filtered_status["recorded_order_value"] = pd.to_numeric(
    filtered_status["recorded_order_value"]
)

total = int(filtered_status["orders"].sum())

cancelled = int(
    filtered_status.loc[
        filtered_status["order_status"] == "Cancelled",
        "orders"
    ].sum()
)

delivered = int(
    filtered_status.loc[
        filtered_status["order_status"] == "Delivered",
        "orders"
    ].sum()
)

delayed = int(
    filtered_status.loc[
        filtered_status["order_status"] == "Delayed",
        "orders"
    ].sum()
)

cancelled_value = float(
    filtered_status.loc[
        filtered_status["order_status"] == "Cancelled",
        "recorded_order_value"
    ].sum()
)

# -------------------------------------------------
# 3. KPI cards
# -------------------------------------------------

c1, c2, c3, c4 = st.columns(4)

c1.metric("Total Orders", f"{total:,}")

c2.metric(
    "Delivered",
    f"{delivered / total * 100:.2f}%"
)

c3.metric(
    "Delayed",
    f"{delayed / total * 100:.2f}%"
)

c4.metric(
    "Cancelled",
    f"{cancelled / total * 100:.2f}%"
)

st.divider()

# -------------------------------------------------
# 4. Order status chart
# -------------------------------------------------

st.subheader("What happened to customer orders?")

left, right = st.columns([1, 1])

with left:
    color_map = {
        "Delivered": GREEN,
        "Delayed": AMBER,
        "Cancelled": RED,
    }

    fig = go.Figure(go.Pie(
        labels=filtered_status["order_status"],
        values=filtered_status["orders"],
        hole=0.65,
        marker=dict(
            colors=[
                color_map.get(x, BLUE)
                for x in filtered_status["order_status"]
            ]
        ),
        textinfo="label+percent"
    ))

    fig.update_layout(
        title="Order Status Breakdown"
    )

    st.plotly_chart(
        style_chart(fig),
        use_container_width=True
    )

with right:
    st.metric(
        "Value of Cancelled Orders",
        format_inr(cancelled_value)
    )

    st.warning(
        "This is the value of orders marked cancelled. "
        "It is NOT confirmed money lost by the business."
    )

    st.write(
        "To measure actual financial loss, we would need "
        "refund, commission and settlement information."
    )

# -------------------------------------------------
# 5. Monthly cancellation trend
# -------------------------------------------------

st.subheader("Are cancellations increasing?")

trend = monthly.copy()

if selected_year != "All years":
    trend = trend.loc[
        trend["order_month"].dt.year == selected_year
    ]

fig = go.Figure()

fig.add_trace(go.Scatter(
    x=trend["order_month"],
    y=trend["cancellation_rate_pct"],
    mode="lines+markers",
    line=dict(color=RED, width=3),
    marker=dict(size=7),
    hovertemplate=(
        "%{x|%b %Y}<br>"
        "%{y:.2f}% cancelled<extra></extra>"
    )
))

fig.update_layout(
    title="Percentage of Orders Cancelled Each Month",
    yaxis_title="Cancelled orders (%)",
    xaxis_title=""
)

st.plotly_chart(
    style_chart(fig),
    use_container_width=True
)

# -------------------------------------------------
# 6. Research-backed insights
# -------------------------------------------------

st.subheader("What did our analysis find?")

insight(
    "Expensive orders are not clearly more likely to cancel",
    "We compared low-, medium- and high-value orders. "
    "Cancellation rates were almost identical, around 10%. "
    "The analysis did not find a meaningful difference."
)

insight(
    "Recorded delivery time needs verification",
    "The dataset includes delivery-time values even for "
    "cancelled orders. We should not assume every recorded "
    "time is the customer's actual delivery time."
)

insight(
    "We cannot yet identify the cause of cancellations",
    "The dataset does not contain cancellation reasons, "
    "courier problems or restaurant acceptance delays. "
    "Without these details, assigning blame would be guesswork."
)

st.divider()

# -------------------------------------------------
# 7. Recommendations
# -------------------------------------------------

st.subheader("What should the operations team do?")

with st.container(border=True):
    st.markdown("**1. Start recording cancellation reasons**")
    st.write(
        "Ask whether the cancellation was caused by "
        "the customer, restaurant, courier or another issue."
    )

with st.container(border=True):
    st.markdown("**2. Track actual delivery milestones**")
    st.write(
        "Record order acceptance, food preparation, "
        "pickup and delivery timestamps."
    )

with st.container(border=True):
    st.markdown("**3. Investigate patterns before taking action**")
    st.write(
        "Avoid penalizing individual restaurants based "
        "on a handful of cancelled orders."
    )

st.caption(
    "Data source: PostgreSQL | "
    "All findings are descriptive, not causal."
)