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
)

st.set_page_config(
    page_title="FoodPulse | Recovery Opportunities",
    page_icon="🎯",
    layout="wide",
)

inject_css()

page_header(
    "Customer recovery / Page 06",
    "Recovery Opportunity Center",
    "Find previously valuable customers who have "
    "not ordered recently and explore who may be "
    "suitable for a test campaign."
)

st.info(
    "These are possible outreach candidates, not "
    "customers guaranteed to return. Past spending "
    "is not future revenue."
)

# --------------------------------------------------
# Load exact validated report
# --------------------------------------------------

@st.cache_data(show_spinner=False)
def get_candidates():
    df = load_report(
        "customer_recovery/recovery_candidate_ranking.csv"
    )

    required = [
        "CustomerID",
        "DaysSinceLastOrder",
        "StableSegment",
        "HistoricalDeliveredValue",
        "RecordedValue",
        "PriorityTier",
        "CandidateRank",
        "RecoveryCandidate",
    ]

    missing = [c for c in required if c not in df.columns]

    if missing:
        raise ValueError(
            f"Missing candidate columns: {missing}"
        )

    for col in [
        "DaysSinceLastOrder",
        "HistoricalDeliveredValue",
        "RecordedValue",
        "CandidateRank",
    ]:
        df[col] = pd.to_numeric(df[col], errors="raise")

    return df


try:
    df = get_candidates()
except Exception as exc:
    st.error("Unable to load the recovery candidate report.")
    st.exception(exc)
    st.stop()

# Normalize tier values so labels work for numeric
# or text-based priority tiers.

def normalize_tier(value):
    text = str(value).strip().lower()

    if text.startswith("tier 1"):
        return "Priority 1"

    if text.startswith("tier 2"):
        return "Priority 2"

    return "Unknown"


df["PriorityGroup"] = df["PriorityTier"].apply(
    normalize_tier
)

# --------------------------------------------------
# Main KPIs
# --------------------------------------------------

st.subheader("Recovery Opportunity Snapshot")

total = len(df)

priority_1 = int(
    (df["PriorityGroup"] == "Priority 1").sum()
)

priority_2 = int(
    (df["PriorityGroup"] == "Priority 2").sum()
)

historical_delivered = float(
    df["HistoricalDeliveredValue"].sum()
)

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Potential Candidates",
    f"{total:,}"
)

c2.metric(
    "Priority 1",
    f"{priority_1:,}"
)

c3.metric(
    "Priority 2",
    f"{priority_2:,}"
)

c4.metric(
    "Past Delivered Order Value",
    format_inr(historical_delivered)
)

st.caption(
    "These figures describe past customer activity. "
    "They do not represent expected campaign revenue."
)

st.divider()

# --------------------------------------------------
# Interactive filters
# --------------------------------------------------

st.subheader("Find the Right Customers")

left, middle, right = st.columns(3)

with left:
    selected_tiers = st.multiselect(
        "Customer priority",
        options=sorted(df["PriorityGroup"].unique()),
        default=sorted(df["PriorityGroup"].unique()),
    )

with middle:
    selected_segments = st.multiselect(
        "Customer group",
        options=sorted(
            df["StableSegment"].dropna().unique()
        ),
        default=sorted(
            df["StableSegment"].dropna().unique()
        ),
    )

with right:
    min_days = st.slider(
        "Minimum days without an order",
        min_value=90,
        max_value=int(df["DaysSinceLastOrder"].max()),
        value=90,
    )

filtered = df.loc[
    df["PriorityGroup"].isin(selected_tiers)
    & df["StableSegment"].isin(selected_segments)
    & (df["DaysSinceLastOrder"] >= min_days)
].copy()

st.caption(
    f"{len(filtered):,} customers match your filters."
)

if filtered.empty:
    st.warning(
        "No customers match these filters. "
        "Try changing your selection."
    )
    st.stop()

# --------------------------------------------------
# Filtered metrics
# --------------------------------------------------

c1, c2, c3 = st.columns(3)

c1.metric(
    "Selected Customers",
    f"{len(filtered):,}"
)

c2.metric(
    "Past Delivered Order Value",
    format_inr(
        filtered["HistoricalDeliveredValue"].sum()
    )
)

c3.metric(
    "Average Days Since Last Order",
    f"{filtered['DaysSinceLastOrder'].mean():.0f}"
)

st.divider()

# --------------------------------------------------
# Visualizations
# --------------------------------------------------

st.subheader("Understand the Opportunity")

left, right = st.columns(2)

with left:
    priority_summary = (
        filtered.groupby("PriorityGroup")
        .agg(Customers=("CustomerID", "nunique"))
        .reset_index()
    )

    fig = px.bar(
        priority_summary,
        x="PriorityGroup",
        y="Customers",
        color="PriorityGroup",
        color_discrete_map={
            "Priority 1": GREEN,
            "Priority 2": BLUE,
        },
        title="Customers by Priority",
        text="Customers",
    )

    fig.update_layout(showlegend=False)

    st.plotly_chart(
        style_chart(fig),
        use_container_width=True
    )

with right:
    segment_summary = (
        filtered.groupby("StableSegment")
        .agg(
            Customers=("CustomerID", "nunique")
        )
        .reset_index()
        .sort_values("Customers")
    )

    fig = px.bar(
        segment_summary,
        x="Customers",
        y="StableSegment",
        orientation="h",
        color_discrete_sequence=[BLUE],
        title="Candidates by Customer Group",
    )

    st.plotly_chart(
        style_chart(fig),
        use_container_width=True
    )

# --------------------------------------------------
# Candidate ranking
# --------------------------------------------------

st.divider()

st.subheader("Top Customers for Review")

st.write(
    "These customers are ranked using the "
    "validated recovery screening method."
)

ranked = filtered.sort_values(
    "CandidateRank"
).copy()

display = ranked[
    [
        "CandidateRank",
        "CustomerID",
        "PriorityGroup",
        "StableSegment",
        "DaysSinceLastOrder",
        "RecordedValue",
        "HistoricalDeliveredValue",
    ]
].head(100)

display.columns = [
    "Rank",
    "Customer ID",
    "Priority",
    "Customer Group",
    "Days Without Order",
    "Past Order Value",
    "Past Delivered Value",
]

st.dataframe(
    display,
    use_container_width=True,
    hide_index=True,
)

# --------------------------------------------------
# Download
# --------------------------------------------------

st.download_button(
    "Download Filtered Candidate List",
    data=ranked.to_csv(index=False).encode("utf-8"),
    file_name="foodpulse_recovery_candidates.csv",
    mime="text/csv",
)

st.caption(
    "This export contains customer IDs and historical "
    "activity only. Check customer contact permissions "
    "before using it for outreach."
)

# --------------------------------------------------
# Insights
# --------------------------------------------------

st.divider()

st.subheader("What Did We Learn?")

insight(
    "A focused group is ready for testing",
    "The analysis identified 2,431 historically "
    "valuable customers who had not ordered "
    "for more than 90 days."
)

insight(
    "Start with customers who ordered frequently",
    "Priority 1 contains 1,939 customers with "
    "strong past order frequency and order value. "
    "They are reasonable candidates for a small "
    "controlled outreach test."
)

insight(
    "Past spending is not recoverable revenue",
    "These customers previously placed delivered "
    "orders worth about ₹2.11 Cr. That amount "
    "does not tell us how much a new campaign "
    "would earn."
)

st.divider()

st.subheader("What Should the Business Do?")

with st.container(border=True):
    st.markdown("**1. Test before scaling**")
    st.write(
        "Run a small campaign with an untreated "
        "comparison group to measure additional orders."
    )

with st.container(border=True):
    st.markdown("**2. Keep campaign costs under control**")
    st.write(
        "Compare extra order contribution with "
        "discounts and messaging costs."
    )

with st.container(border=True):
    st.markdown("**3. Measure actual results**")
    st.write(
        "Track additional orders, spending and "
        "customer responses instead of assuming "
        "every returning customer was recovered."
    )

st.caption(
    "Source: Validated priority_recovery_candidates.csv"
)