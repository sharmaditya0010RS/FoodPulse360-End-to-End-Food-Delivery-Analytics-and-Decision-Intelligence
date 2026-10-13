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
    GREEN,
    BLUE,
    AMBER,
    RED,
)

st.set_page_config(
    page_title="FoodPulse | Data Trust",
    page_icon="🛡️",
    layout="wide",
)

inject_css()

page_header(
    "Transparency / Page 08",
    "Data Trust Center",
    "Understand where the numbers come from, "
    "what we checked, and which findings "
    "need extra care."
)

st.info(
    "Good business decisions need trustworthy data. "
    "This page explains the limitations "
    "in plain language."
)

# --------------------------------------------------
# Warehouse checks
# --------------------------------------------------

@st.cache_data(ttl=300)
def load_checks():
    return query_data("""
        SELECT
            COUNT(*) AS total_orders,
            COUNT(DISTINCT "OrderID")
                AS unique_orders,
            COUNT(DISTINCT "CustomerID")
                AS customers,
            COUNT(DISTINCT "RestaurantID")
                AS restaurants,
            SUM(recorded_order_value)
                AS recorded_value,
            SUM(confirmed_delivered_value)
                AS delivered_value,
            COUNT(*) FILTER (
                WHERE order_before_signup = TRUE
            ) AS chronology_flags
        FROM foodpulse.fact_orders
    """)


checks = load_checks().iloc[0]

total_orders = int(checks["total_orders"])
unique_orders = int(checks["unique_orders"])
customers = int(checks["customers"])
restaurants = int(checks["restaurants"])
chronology = int(checks["chronology_flags"])

st.subheader("Data Quality Snapshot")

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Orders Checked",
    f"{total_orders:,}"
)

c2.metric(
    "Unique Order IDs",
    f"{unique_orders:,}"
)

c3.metric(
    "Customers",
    f"{customers:,}"
)

c4.metric(
    "Restaurants with Orders",
    f"{restaurants:,}"
)

if total_orders == unique_orders:
    st.success(
        "Every order has a unique order ID."
    )
else:
    st.error(
        "Duplicate order IDs were found."
    )

st.divider()

# --------------------------------------------------
# Data issues
# --------------------------------------------------

st.subheader("What Problems Did We Find?")

issues = pd.DataFrame({
    "Issue": [
        "Orders before signup",
        "Restaurants with suspicious information",
        "Orders linked to flagged restaurants",
        "Restaurants with no recorded orders",
    ],
    "Count": [
        chronology,
        4519,
        15859,
        1650,
    ],
})

fig = go.Figure()

fig.add_trace(go.Bar(
    x=issues["Count"],
    y=issues["Issue"],
    orientation="h",
    marker_color=[
        RED,
        AMBER,
        BLUE,
        GREEN,
    ],
    text=issues["Count"],
    textposition="outside",
))

fig.update_layout(
    title="Important Data Issues Found",
    xaxis_title="Number of records",
    yaxis_title="",
)

st.plotly_chart(
    style_chart(fig, height=440),
    use_container_width=True
)

st.caption(
    "These counts describe different types of records "
    "and should not be added together."
)

# --------------------------------------------------
# Simple explanations
# --------------------------------------------------

st.divider()
st.subheader("Why Do These Issues Matter?")

insight(
    "Some orders appear before customer signup",
    "18,372 orders have dates earlier than the "
    "customer's recorded signup date. "
    "This may mean signup dates or customer history "
    "are incomplete or inconsistent."
)

insight(
    "Some restaurant information looks incorrect",
    "4,519 restaurant records contain suspected "
    "scraped-text contamination. Restaurant names, "
    "ratings or categories may not be trustworthy "
    "for those records."
)

insight(
    "The latest month is incomplete",
    "The dataset ends on September 26, 2025. "
    "Comparing that partial month against "
    "a full month can create a false decline."
)

insight(
    "Customer history may start before our dataset",
    "We know when customers first appear in "
    "these records, but not necessarily when "
    "they first became customers."
)

st.divider()

# --------------------------------------------------
# Metric dictionary
# --------------------------------------------------

st.subheader("What Do the Dashboard Numbers Mean?")

definitions = pd.DataFrame({
    "Dashboard Term": [
        "Total Orders",
        "Recorded Order Value",
        "Delivered Order Value",
        "Cancellation Rate",
        "Active Customer",
        "Inactive Customer",
        "Recovery Candidate",
        "Estimated Campaign Result",
    ],
    "Simple Meaning": [
        "Number of orders in the dataset",
        "Total amount shown on recorded orders",
        "Total amount shown on delivered-status orders",
        "Percentage of orders marked cancelled",
        "Customer who ordered in the selected activity window",
        "Customer who has not ordered recently",
        "Previously valuable customer selected for outreach review",
        "What-if result based on user-entered assumptions",
    ],
})

st.dataframe(
    definitions,
    use_container_width=True,
    hide_index=True
)

# --------------------------------------------------
# Recommendations
# --------------------------------------------------

st.divider()
st.subheader("What Should the Business Improve?")

with st.container(border=True):
    st.markdown("**1. Fix customer signup dates**")
    st.write(
        "Check account creation records and "
        "correct impossible order timelines."
    )

with st.container(border=True):
    st.markdown("**2. Verify restaurant information**")
    st.write(
        "Review restaurant names, ratings and "
        "categories before using them in rankings."
    )

with st.container(border=True):
    st.markdown("**3. Collect actual financial information**")
    st.write(
        "Add commissions, refunds, discounts and costs "
        "before reporting company revenue or profit."
    )

with st.container(border=True):
    st.markdown("**4. Track customer and delivery events**")
    st.write(
        "Capture complete customer histories, "
        "delivery milestones and cancellation reasons "
        "to support stronger business decisions."
    )

st.caption(
    "Data quality counts come from the validated "
    "FoodPulse 360 analysis and PostgreSQL warehouse."
)