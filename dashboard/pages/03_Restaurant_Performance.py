from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

import pandas as pd
import plotly.express as px
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
    page_title="FoodPulse | Restaurant Performance",
    page_icon="🍴",
    layout="wide",
)

inject_css()

page_header(
    "Restaurant intelligence / Page 03",
    "Restaurant Performance Hub",
    "Find strong restaurant partners, understand order "
    "performance, and spot issues worth investigating."
)

st.info(
    "A restaurant with many orders is not necessarily "
    "more profitable. This page measures order activity "
    "and order value, not restaurant profit."
)


@st.cache_data(ttl=300)
def get_restaurants():
    return query_data("""
        SELECT
            "RestaurantID" AS restaurant_id,
            "restaurant_name" AS restaurant_name,
            "restaurant_location" AS location,
            "restaurant_type" AS restaurant_type,
            "restaurant_quality_flag" AS quality_flag,
            orders,
            recorded_order_value,
            delivered_order_value,
            cancelled_orders,
            cancellation_rate_pct
        FROM foodpulse.vw_restaurant_performance
    """)


df = get_restaurants()

for col in [
    "orders",
    "recorded_order_value",
    "delivered_order_value",
    "cancelled_orders",
    "cancellation_rate_pct",
]:
    df[col] = pd.to_numeric(df[col], errors="raise")

# Source quality flag may be null for some records.
df["quality_flag"] = (
    df["quality_flag"]
    .astype("string")
    .str.lower()
    .isin(["true", "1"])
)

# Some restaurant attributes contain scraped text.
# Keep quality-flagged records in overall totals,
# but hide them from named restaurant rankings.

clean = df.loc[~df["quality_flag"]].copy()

st.subheader("Restaurant Network")

total_restaurants = len(df)
total_orders = int(df["orders"].sum())
total_value = float(df["recorded_order_value"].sum())
flagged = int(df["quality_flag"].sum())

c1, c2, c3, c4 = st.columns(4)

c1.metric(
    "Restaurants with Orders",
    f"{total_restaurants:,}"
)

c2.metric(
    "Orders from Restaurants",
    f"{total_orders:,}"
)

c3.metric(
    "Total Order Value",
    format_inr(total_value)
)

c4.metric(
    "Restaurants Needing Data Review",
    f"{flagged:,}"
)

st.caption(
    "These totals include all restaurants with orders. "
    "The original restaurant list also contains "
    "1,650 restaurants with no recorded orders."
)

st.divider()

# -------------------------------------------------
# Filters
# -------------------------------------------------

st.subheader("Explore Restaurant Partners")

left, right = st.columns([1, 1])

with left:
    min_orders = st.slider(
        "Minimum number of orders",
        min_value=1,
        max_value=15,
        value=5,
        help=(
            "Show only restaurants with at least "
            "this many orders."
        )
    )

with right:
    sort_option = st.selectbox(
        "Rank restaurants by",
        [
            "Total order value",
            "Number of orders",
            "Delivered order value",
        ]
    )

sort_columns = {
    "Total order value": "recorded_order_value",
    "Number of orders": "orders",
    "Delivered order value": "delivered_order_value",
}

sort_col = sort_columns[sort_option]

ranked = clean.loc[
    clean["orders"] >= min_orders
].copy()

ranked = ranked.sort_values(
    [sort_col, "restaurant_id"],
    ascending=[False, True]
)

st.caption(
    f"Showing {len(ranked):,} restaurants with "
    "usable source attributes that meet your filter."
)

# -------------------------------------------------
# Top restaurants
# -------------------------------------------------

st.subheader("Top Restaurant Partners")

top = ranked.head(15).copy()

if not top.empty:
    top["DisplayName"] = (
        top["restaurant_name"]
        .fillna("Unnamed restaurant")
        .astype(str)
        .str.slice(0, 45)
        + " · #"
        + top["restaurant_id"].astype(str)
    )

    fig = px.bar(
        top.sort_values(sort_col),
        x=sort_col,
        y="DisplayName",
        orientation="h",
        color_discrete_sequence=[GREEN],
        title=f"Top 15 by {sort_option}",
        labels={
            sort_col: sort_option,
            "DisplayName": "Restaurant",
        },
    )

    st.plotly_chart(
        style_chart(fig, height=560),
        use_container_width=True
    )
else:
    st.warning(
        "No restaurants match this filter. "
        "Try reducing the minimum order count."
    )

# -------------------------------------------------
# Restaurant concentration
# -------------------------------------------------

st.divider()
st.subheader("Is business dependent on a few restaurants?")

insight(
    "Orders are spread across many restaurants",
    "The top 10% of restaurants account for about "
    "21.05% of recorded order value. This suggests "
    "the marketplace is not heavily dependent on "
    "a small group of restaurants."
)

insight(
    "Most restaurants have very few orders",
    "Many restaurants have only one to five orders "
    "in the dataset. This makes individual "
    "cancellation percentages unreliable."
)

# -------------------------------------------------
# Cancellation investigation
# -------------------------------------------------

st.divider()
st.subheader("Restaurants Worth Monitoring")

st.write(
    "A high cancellation percentage based on only "
    "a few orders can be misleading. The list below "
    "is for investigation, not punishment."
)

monitor = clean.loc[
    clean["orders"] >= 10
].copy()

monitor = monitor.sort_values(
    ["cancellation_rate_pct", "orders"],
    ascending=[False, False]
)

monitor_display = monitor[
    [
        "restaurant_id",
        "restaurant_name",
        "orders",
        "cancelled_orders",
        "cancellation_rate_pct",
    ]
].head(15).copy()

monitor_display.columns = [
    "Restaurant ID",
    "Restaurant",
    "Total Orders",
    "Cancelled Orders",
    "Cancellation (%)",
]

st.dataframe(
    monitor_display,
    use_container_width=True,
    hide_index=True,
)

st.warning(
    "Important: The statistical review found "
    "no restaurant with a confirmed unusually high "
    "cancellation rate after correcting for "
    "multiple comparisons. This table is descriptive."
)

# -------------------------------------------------
# Recommendations
# -------------------------------------------------

st.divider()
st.subheader("What should the business do?")

with st.container(border=True):
    st.markdown("**1. Help restaurants with low activity**")
    st.write(
        "Check whether restaurants with very few orders "
        "have menu, visibility or availability issues."
    )

with st.container(border=True):
    st.markdown("**2. Review cancellations fairly**")
    st.write(
        "Investigate restaurants only after collecting "
        "enough orders and understanding cancellation reasons."
    )

with st.container(border=True):
    st.markdown("**3. Fix restaurant information**")
    st.write(
        "Clean incorrect names, ratings and categories "
        "before using them in restaurant rankings."
    )

st.caption(
    "Source: PostgreSQL + validated restaurant analysis. "
    "No restaurant is classified as statistically proven high-risk."
)