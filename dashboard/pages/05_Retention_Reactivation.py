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
    page_title="FoodPulse | Customer Activity",
    page_icon="🔄",
    layout="wide",
)

inject_css()

page_header(
    "Customer relationships / Page 05",
    "Retention & Reactivation",
    "See which customers are still ordering, "
    "who has stopped ordering recently, "
    "and where follow-up may help."
)

st.info(
    "All activity is measured up to the last date "
    "in our dataset — not today's date. "
    "This is a historical analysis."
)


@st.cache_data(ttl=300)
def load_activity():
    return query_data("""
        SELECT
            "CustomerID" AS customer_id,
            historical_orders,
            historical_recorded_value,
            historical_delivered_value,
            first_observed_order,
            last_observed_order,
            days_since_last_order
        FROM foodpulse.vw_customer_activity
    """)


@st.cache_data(ttl=300)
def load_dataset_end():
    return query_data("""
        SELECT MAX(order_date)::DATE AS dataset_end
        FROM foodpulse.fact_orders
    """).iloc[0]["dataset_end"]


df = load_activity()

for column in [
    "historical_orders",
    "historical_recorded_value",
    "historical_delivered_value",
    "days_since_last_order",
]:
    df[column] = pd.to_numeric(
        df[column],
        errors="raise"
    )

dataset_end = load_dataset_end()

# -------------------------------------------------
# Activity groups
# -------------------------------------------------

def activity_group(days):
    if days <= 30:
        return "Active: Last 30 Days"
    if days <= 90:
        return "Inactive: 31–90 Days"
    if days <= 180:
        return "Inactive: 91–180 Days"
    return "Inactive: Over 180 Days"


df["activity_group"] = df[
    "days_since_last_order"
].apply(activity_group)

group_order = [
    "Active: Last 30 Days",
    "Inactive: 31–90 Days",
    "Inactive: 91–180 Days",
    "Inactive: Over 180 Days",
]

summary = (
    df.groupby("activity_group")
    .agg(
        customers=("customer_id", "nunique"),
        historical_orders=("historical_orders", "sum"),
        historical_value=(
            "historical_recorded_value",
            "sum"
        ),
    )
    .reindex(group_order, fill_value=0)
    .reset_index()
)

# -------------------------------------------------
# KPIs
# -------------------------------------------------

st.subheader("How Active Are Our Customers?")

total = len(df)

active = int(
    (df["days_since_last_order"] <= 30).sum()
)

inactive_90 = int(
    (df["days_since_last_order"] > 90).sum()
)

repeat_customers = int(
    (df["historical_orders"] >= 2).sum()
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Customers",
    f"{total:,}"
)

c2.metric(
    "Ordered in Last 30 Days",
    f"{active:,}"
)

c3.metric(
    "No Order for Over 90 Days",
    f"{inactive_90:,}"
)

c4.metric(
    "Customers with 2+ Orders",
    f"{repeat_customers:,}"
)

st.caption(
    f"Activity reference date: {dataset_end}. "
    "These figures describe historical customer behavior."
)

st.divider()

# -------------------------------------------------
# Activity distribution
# -------------------------------------------------

st.subheader("When Did Customers Last Order?")

fig = go.Figure()

fig.add_trace(go.Bar(
    x=summary["activity_group"],
    y=summary["customers"],
    marker_color=[
        GREEN,
        BLUE,
        AMBER,
        RED,
    ],
    text=summary["customers"],
    textposition="outside",
    hovertemplate=(
        "%{x}<br>"
        "%{y:,} customers<extra></extra>"
    )
))

fig.update_layout(
    title="Customers by Time Since Their Last Order",
    xaxis_title="",
    yaxis_title="Number of customers",
)

st.plotly_chart(
    style_chart(fig, height=440),
    use_container_width=True
)

st.caption(
    "A customer who has not ordered recently is "
    "called inactive here. This does not prove "
    "they have permanently left the business."
)

# -------------------------------------------------
# Interactive exploration
# -------------------------------------------------

st.divider()
st.subheader("Explore Customer Activity")

selected_groups = st.multiselect(
    "Choose customer groups",
    options=group_order,
    default=group_order,
)

if not selected_groups:
    st.warning("Please select at least one group.")
    st.stop()

filtered = df.loc[
    df["activity_group"].isin(selected_groups)
].copy()

c1, c2 = st.columns(2)

c1.metric(
    "Customers in Selected Groups",
    f"{len(filtered):,}"
)

c2.metric(
    "Average Historical Orders per Customer",
    f"{filtered['historical_orders'].mean():.1f}"
)

display = (
    filtered[
        [
            "customer_id",
            "historical_orders",
            "days_since_last_order",
            "activity_group",
        ]
    ]
    .sort_values(
        ["days_since_last_order", "historical_orders"],
        ascending=[False, False]
    )
    .head(100)
)

display.columns = [
    "Customer ID",
    "Past Orders",
    "Days Since Last Order",
    "Customer Activity Group",
]

with st.expander("View sample customer records"):
    st.dataframe(
        display,
        use_container_width=True,
        hide_index=True
    )

    st.caption(
        "Showing up to 100 historical records. "
        "Customer IDs are for internal analysis only."
    )

# -------------------------------------------------
# Retention findings
# -------------------------------------------------

st.divider()
st.subheader("What Did We Learn?")

insight(
    "Most customers ordered more than once",
    "19,989 of 20,000 customers have at least "
    "two recorded orders. This shows repeated "
    "activity within our dataset, but it does not "
    "prove a 99.94% real-world retention rate."
)

insight(
    "Some customers have been inactive for months",
    "8,053 customers had no recorded order for "
    "more than 90 days before the dataset ended. "
    "They are worth studying for possible outreach."
)

insight(
    "Our retention numbers need careful interpretation",
    "Many customers already appear near the beginning "
    "of the dataset. We cannot reliably tell when "
    "they first joined the business."
)

st.divider()

# -------------------------------------------------
# Recommendations
# -------------------------------------------------

st.subheader("What Should the Business Do?")

with st.container(border=True):
    st.markdown("**1. Understand why customers stop ordering**")
    st.write(
        "Collect customer feedback and check for "
        "delivery problems, poor experiences, "
        "or changing preferences."
    )

with st.container(border=True):
    st.markdown("**2. Test reminders with inactive customers**")
    st.write(
        "Start with a small group and compare "
        "their results with customers who "
        "received no reminder."
    )

with st.container(border=True):
    st.markdown("**3. Improve customer history data**")
    st.write(
        "Record verified signup dates and "
        "complete earlier order history before "
        "measuring true customer retention."
    )

st.caption(
    "Source: PostgreSQL customer activity view. "
    "All conclusions are based on observed history."
)