import html

import plotly.graph_objects as go
import streamlit as st


BG = "#080F1E"
PANEL = "#111D31"
BORDER = "#263650"
TEXT = "#F1F5F9"
MUTED = "#94A3B8"
GREEN = "#34D399"
BLUE = "#60A5FA"
AMBER = "#FBBF24"
RED = "#FB7185"


def inject_css():
    st.markdown(
        """
        <style>
        @import url(
          'https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Manrope:wght@500;600;700;800&display=swap'
        );

        html, body, [class*="css"] {
            font-family: 'DM Sans', sans-serif;
        }

        .stApp {
            background:
                radial-gradient(
                    ellipse at 85% 0%,
                    rgba(52, 211, 153, .075),
                    transparent 34%
                ),
                #080F1E;
        }

        h1, h2, h3 {
            font-family: 'Manrope', sans-serif;
            letter-spacing: -.035em;
        }

        h1 {
            font-weight: 800 !important;
        }

        [data-testid="stSidebar"] {
            background: #0C1729;
            border-right: 1px solid #263650;
        }

        [data-testid="stMetric"] {
            background: linear-gradient(
                145deg, #15243A, #101B2D
            );
            padding: 20px;
            border: 1px solid #263650;
            border-radius: 16px;
            min-height: 130px;
        }

        [data-testid="stMetricLabel"] {
            color: #94A3B8;
        }

        [data-testid="stMetricValue"] {
            font-family: 'Manrope', sans-serif;
            font-weight: 800;
            letter-spacing: -.04em;
        }

        div[data-testid="stPlotlyChart"] {
            border: 1px solid #263650;
            border-radius: 16px;
            background: #111D31;
            padding: 10px;
        }

        div.stButton > button {
            border-radius: 10px;
            border: 1px solid #34536A;
        }

        div[data-testid="stAlert"] {
            border-radius: 12px;
        }

        .fp-eyebrow {
            color: #34D399;
            font-size: .75rem;
            font-weight: 800;
            letter-spacing: .17em;
            text-transform: uppercase;
        }

        .fp-subtitle {
            color: #94A3B8;
            font-size: 1rem;
            margin-bottom: 22px;
        }

        .fp-insight {
            background: #111D31;
            border: 1px solid #263650;
            border-left: 3px solid #34D399;
            padding: 18px 20px;
            border-radius: 12px;
            margin: 10px 0;
        }

        .fp-insight-title {
            color: #F1F5F9;
            font-weight: 800;
            margin-bottom: 6px;
        }

        .fp-insight-body {
            color: #CBD5E1;
            line-height: 1.6;
        }

        .fp-brand {
            color: #F1F5F9;
            font-size: 1.5rem;
            font-weight: 800;
            letter-spacing: -.05em;
        }

        .fp-brand span {
            color: #34D399;
        }

        #MainMenu {visibility: hidden;}
        footer {visibility: hidden;}
        </style>
        """,
        unsafe_allow_html=True
    )


def page_header(eyebrow, title, subtitle):
    st.markdown(
        f'<div class="fp-eyebrow">'
        f'{html.escape(eyebrow)}</div>',
        unsafe_allow_html=True
    )
    st.title(title)
    st.markdown(
        f'<div class="fp-subtitle">'
        f'{html.escape(subtitle)}</div>',
        unsafe_allow_html=True
    )


def insight(title, body):
    st.markdown(
        f"""
        <div class="fp-insight">
            <div class="fp-insight-title">
                {html.escape(title)}
            </div>
            <div class="fp-insight-body">
                {html.escape(body)}
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )


def style_chart(fig, height=380):
    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor=PANEL,
        plot_bgcolor=PANEL,
        font=dict(
            family="DM Sans",
            color=TEXT,
            size=12
        ),
        height=height,
        margin=dict(l=25, r=20, t=65, b=35),
        title_font=dict(size=17),
        hoverlabel=dict(
            bgcolor="#1E293B",
            font_color=TEXT
        ),
        xaxis=dict(
            showgrid=False,
            zeroline=False
        ),
        yaxis=dict(
            gridcolor="#263650",
            zeroline=False
        ),
        legend=dict(
            orientation="h",
            y=-0.22
        )
    )

    return fig


def format_inr(value):
    value = float(value)

    if abs(value) >= 10_000_000:
        return f"₹{value / 10_000_000:,.2f} Cr"

    if abs(value) >= 100_000:
        return f"₹{value / 100_000:,.2f} L"

    return f"₹{value:,.0f}"


def sidebar():
    with st.sidebar:
        st.markdown(
            '<div class="fp-brand">FOOD<span>PULSE</span> 360</div>',
            unsafe_allow_html=True
        )
        st.caption("ENTERPRISE INTELLIGENCE / V2.0")
        st.divider()

        st.caption("Navigate using the page links above or below.")

        if st.button(
            "↻ Refresh warehouse data",
            use_container_width=True
        ):
            from dashboard.core.database import refresh_data
            refresh_data()
            st.rerun()

        st.divider()
        st.caption("SOURCE: PostgreSQL + validated reports")
        st.caption("OBSERVATION: 2023–2025")
        st.caption("FINANCIAL VALUES: order face value, not revenue")