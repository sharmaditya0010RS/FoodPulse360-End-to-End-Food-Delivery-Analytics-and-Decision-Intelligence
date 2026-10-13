from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
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
    page_title="FoodPulse | Customer Intelligence",
    page_icon="👥",
    layout="wide",
)

inject_css()

page_header(
    "Customer intelligence / Page 04",
    "Customer Intelligence Studio",
    "Understand who your customers are, how often "
    "they order, and which groups need attention."
)

st.info(
    "Customer groups are based on their past ordering "
    "behavior. These are helpful descriptions, "
    "not predictions of what someone will do next."
)

# -------------------------------------------------
# Load validated RFM reports
# -------------------------------------------------

segments = load_report(
    "rfm_stability/stable_segment_summary.csv"
)

customers = load_report(
    "rfm_stability/stable_customer_rfm.csv"
)

assert len(customers) == 20000

required = [
    "StableSegment",
    "Customers",
    "Orders",
    "RecordedValue",
    "DeliveredValue",
    "CustomerSharePct",
    "RecordedValueSharePct",
]

missing = [
    c for c in required
    if c not in segments.columns
]

if missing:
    st.error(f"Missing report fields: {missing}")
    st.stop()

# -------------------------------------------------
# Main metrics
# -------------------------------------------------

st.subheader("Customer Overview")

total_customers = int(segments["Customers"].sum())
total_orders = int(segments["Orders"].sum())
total_value = float(segments["RecordedValue"].sum())

champions = int(
    segments.loc[
        segments["StableSegment"] == "Champions",
        "Customers"
    ].sum()
)

at_risk = int(
    segments.loc[
        segments["StableSegment"] == "At Risk",
        "Customers"
    ].sum()
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Total Customers",
    f"{total_customers:,}"
)

c2.metric(
    "Total Orders",
    f"{total_orders:,}"
)

c3.metric(
    "Top Customer Group",
    f"{champions:,}",
    help="Customers in the Champions group."
)

c4.metric(
    "Customers Needing Attention",
    f"{at_risk:,}",
    help="Customers classified as At Risk."
)

st.divider()

# -------------------------------------------------
# Simple segment explanations
# -------------------------------------------------

descriptions = {
    "Champions": (
        "Customers who order often, have ordered recently, "
        "and have high historical order value."
    ),
    "At Risk": (
        "Previously valuable customers who have not "
        "ordered recently."
    ),
    "High Value Regulars": (
        "Customers with strong order history and "
        "high historical order value."
    ),
    "Core Customers": (
        "Regular customers who form an important "
        "part of the business."
    ),
    "Promising Occasional": (
        "Customers who ordered recently but "
        "have ordered less often."
    ),
    "Low Engagement": (
        "Customers who order less frequently "
        "or have not ordered recently."
    ),
}

st.subheader("Explore Customer Groups")

selected = st.multiselect(
    "Choose customer groups",
    options=segments["StableSegment"].tolist(),
    default=segments["StableSegment"].tolist()
)

if not selected:
    st.warning("Choose at least one customer group.")
    st.stop()

filtered = segments.loc[
    segments["StableSegment"].isin(selected)
].copy()

# -------------------------------------------------
# Charts
# -------------------------------------------------

left, right = st.columns(2)

with left:
    fig = px.bar(
        filtered.sort_values("Customers"),
        x="Customers",
        y="StableSegment",
        orientation="h",
        color_discrete_sequence=[BLUE],
        title="How Many Customers Are in Each Group?",
        labels={
            "StableSegment": "Customer group",
            "Customers": "Number of customers",
        },
    )

    st.plotly_chart(
        style_chart(fig, height=430),
        use_container_width=True
    )

with right:
    fig = px.bar(
        filtered.sort_values("RecordedValue"),
        x="RecordedValue",
        y="StableSegment",
        orientation="h",
        color_discrete_sequence=[GREEN],
        title="Historical Order Value by Group",
        labels={
            "StableSegment": "Customer group",
            "RecordedValue": "Recorded order value (₹)",
        },
    )

    st.plotly_chart(
        style_chart(fig, height=430),
        use_container_width=True
    )

st.caption(
    "Historical order value is not future revenue "
    "or money that can automatically be recovered."
)

# -------------------------------------------------
# Segment cards
# -------------------------------------------------

st.divider()
st.subheader("What Does Each Customer Group Mean?")

for _, row in filtered.sort_values(
    "Customers",
    ascending=False
).iterrows():

    name = row["StableSegment"]

    with st.expander(
        f"{name} · {int(row['Customers']):,} customers"
    ):
        st.write(
            descriptions.get(
                name,
                "Customers grouped by past ordering behavior."
            )
        )

        c1, c2 = st.columns(2)

        c1.metric(
            "Customers",
            f"{int(row['Customers']):,}"
        )

        c2.metric(
            "Historical Order Value",
            format_inr(row["RecordedValue"])
        )

# -------------------------------------------------
# Main insights
# -------------------------------------------------

st.divider()
st.subheader("What Did We Learn?")

insight(
    "Champions are an important customer group",
    "3,416 Champions account for approximately "
    "23.74% of all recorded order value. "
    "Keeping these customers engaged is important."
)

insight(
    "Some valuable customers are becoming inactive",
    "2,419 customers are in the At Risk group. "
    "This is a useful group to study before planning "
    "a customer re-engagement campaign."
)

insight(
    "Customer scoring was checked for fairness",
    "The original method could give different scores "
    "to customers with the same order behavior. "
    "The updated method gives equal behavior equal scores."
)

# -------------------------------------------------
# Recommendations
# -------------------------------------------------

st.divider()
st.subheader("What Should the Business Do?")

with st.container(border=True):
    st.markdown("**1. Keep your best customers happy**")
    st.write(
        "Test loyalty benefits, reliable delivery and "
        "personalized offers for frequent customers."
    )

with st.container(border=True):
    st.markdown("**2. Reach out to inactive customers carefully**")
    st.write(
        "Start with a small test campaign. "
        "Compare results against customers who "
        "did not receive an offer."
    )

with st.container(border=True):
    st.markdown("**3. Help occasional customers order again**")
    st.write(
        "Explore reminders and relevant recommendations, "
        "without assuming they will increase orders."
    )

st.caption(
    "Source: Validated stable RFM reports. "
    "Customer groups are descriptive, not predictive."
)