
from pathlib import Path
import ast
import os
import sys

import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

PASS = 0
FAIL = 0
WARN = 0


def check(name, condition, detail=""):
    global PASS, FAIL

    if condition:
        PASS += 1
        print(f"[PASS] {name}")
    else:
        FAIL += 1
        print(f"[FAIL] {name}")

    if detail:
        print(f"       {detail}")


def warning(message):
    global WARN
    WARN += 1
    print(f"[WARN] {message}")


def number(value):
    return float(value or 0)


def close(a, b, tolerance=0.01):
    return abs(number(a) - number(b)) <= tolerance


print("=" * 65)
print("FOODPULSE 360 V2.0 - DASHBOARD QUALITY ASSURANCE")
print("=" * 65)

# --------------------------------------------------
# 1. Dashboard files and syntax
# --------------------------------------------------

print("\n[1] DASHBOARD FILES")

dashboard_files = [
    "dashboard/app.py",
    "dashboard/core/database.py",
    "dashboard/core/design.py",
    "dashboard/pages/01_Revenue_Growth.py",
    "dashboard/pages/02_Delivery_Cancellation.py",
    "dashboard/pages/03_Restaurant_Performance.py",
    "dashboard/pages/04_Customer_Intelligence.py",
    "dashboard/pages/05_Retention_Reactivation.py",
    "dashboard/pages/06_Recovery_Opportunities.py",
    "dashboard/pages/07_Scenario_Simulator.py",
    "dashboard/pages/08_Data_Trust.py",
]

for relative_path in dashboard_files:
    path = ROOT / relative_path

    if not path.is_file():
        check(relative_path, False, "File missing")
        continue

    try:
        source = path.read_text(encoding="utf-8-sig")
        ast.parse(source, filename=str(path))
        check(relative_path, True)
    except (SyntaxError, UnicodeError, OSError) as exc:
        check(relative_path, False, str(exc))


# --------------------------------------------------
# 2. Required reports
# --------------------------------------------------

print("\n[2] ANALYTICS REPORTS")

report_files = [
    "data/reports/rfm_stability/stable_customer_rfm.csv",
    "data/reports/customer_recovery/customer_recovery_scorecard.csv",
    "data/reports/customer_recovery/priority_recovery_candidates.csv",
    "data/reports/customer_recovery/recovery_by_rfm_segment.csv",
    "data/reports/customer_recovery/recovery_candidate_ranking.csv",
    "data/reports/customer_recovery/recovery_opportunity_summary.csv",
]

for relative_path in report_files:
    check(
        relative_path,
        (ROOT / relative_path).is_file()
    )


# --------------------------------------------------
# 3. PostgreSQL connection
# --------------------------------------------------

print("\n[3] POSTGRESQL CONNECTION")

required_env = [
    "PGHOST",
    "PGPORT",
    "PGDATABASE",
    "PGUSER",
    "PGPASSWORD",
]

env = {key: (os.getenv(key) or "") for key in required_env}
missing = [key for key, value in env.items() if not value]

if missing:
    check(
        "Database configuration",
        False,
        f"Missing environment variables: {missing}"
    )
    print("\nQA stopped: database credentials missing.")
    sys.exit(1)

engine = None

try:
    pg_port = int(env["PGPORT"])
    url = URL.create(
        "postgresql+psycopg",
        username=env["PGUSER"],
        password=env["PGPASSWORD"],
        host=env["PGHOST"],
        port=pg_port,
        database=env["PGDATABASE"],
    )

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 10},
    )

    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))

    check("PostgreSQL connection", True)

except Exception as exc:
    check("PostgreSQL connection", False, str(exc))
    print("\nQA stopped: database unavailable.")
    sys.exit(1)


def sql_df(query):
    if engine is None:
        raise RuntimeError("Database engine is not initialized.")

    with engine.connect() as conn:
        return pd.read_sql_query(text(query), conn)


# --------------------------------------------------
# 4. Warehouse tables and views
# --------------------------------------------------

print("\n[4] WAREHOUSE TABLES AND VIEWS")

objects = [
    "fact_orders",
    "dim_customers",
    "dim_restaurants",
    "dim_dates",
    "vw_executive_kpis",
    "vw_monthly_performance",
    "vw_order_status",
    "vw_customer_activity",
    "vw_restaurant_performance",
]

existing = sql_df("""
    SELECT table_name
    FROM information_schema.tables
    WHERE table_schema = 'foodpulse'
""")

existing_names = set(existing["table_name"].tolist())

for obj in objects:
    check(
        f"foodpulse.{obj}",
        obj in existing_names
    )


# --------------------------------------------------
# 5. Executive KPI reconciliation
# --------------------------------------------------

print("\n[5] EXECUTIVE KPI CHECKS")

kpi = sql_df("""
    SELECT *
    FROM foodpulse.vw_executive_kpis
""").iloc[0]

fact = sql_df("""
    SELECT
        COUNT(*) AS orders,
        COUNT(DISTINCT "OrderID") AS unique_orders,
        COUNT(DISTINCT "CustomerID") AS customers,
        COUNT(DISTINCT "RestaurantID") AS restaurants,
        SUM(recorded_order_value) AS recorded_value,
        SUM(confirmed_delivered_value) AS delivered_value,
        COUNT(*) FILTER (
            WHERE is_cancelled = TRUE
        ) AS cancelled_orders,
        COUNT(*) FILTER (
            WHERE order_before_signup = TRUE
        ) AS chronology_flags,
        MIN(order_date)::DATE AS first_date,
        MAX(order_date)::DATE AS last_date
    FROM foodpulse.fact_orders
""").iloc[0]

check(
    "200,000 orders",
    int(fact["orders"]) == 200000
)

check(
    "Unique order IDs",
    int(fact["orders"]) == int(fact["unique_orders"])
)

check(
    "20,000 customers",
    int(fact["customers"]) == 20000
)

check(
    "54,600 restaurants with orders",
    int(fact["restaurants"]) == 54600
)

check(
    "Executive order count matches fact table",
    int(kpi["total_orders"]) == int(fact["orders"])
)

check(
    "Executive customer count matches",
    int(kpi["active_customers"]) == int(fact["customers"])
)

check(
    "Executive restaurant count matches",
    int(kpi["active_restaurants"]) == int(fact["restaurants"])
)

check(
    "Recorded order value matches",
    close(
        kpi["recorded_order_value"],
        fact["recorded_value"]
    )
)

check(
    "Delivered order value matches",
    close(
        kpi["delivered_order_value"],
        fact["delivered_value"]
    )
)

check(
    "Cancellation count matches",
    int(kpi["cancelled_orders"]) ==
    int(fact["cancelled_orders"])
)

check(
    "Chronology flags match",
    int(kpi["chronology_flagged_orders"]) ==
    int(fact["chronology_flags"])
)

check(
    "Expected observation end",
    str(fact["last_date"]) == "2025-09-26"
)


# --------------------------------------------------
# 6. Monthly and status reconciliation
# --------------------------------------------------

print("\n[6] MONTHLY AND STATUS CHECKS")

monthly = sql_df("""
    SELECT *
    FROM foodpulse.vw_monthly_performance
    ORDER BY order_month
""")

status = sql_df("""
    SELECT *
    FROM foodpulse.vw_order_status
""")

check(
    "33 monthly periods",
    len(monthly) == 33
)

check(
    "Monthly orders match executive",
    int(monthly["orders"].sum()) ==
    int(kpi["total_orders"])
)

check(
    "Monthly recorded value matches",
    close(
        monthly["recorded_order_value"].sum(),
        kpi["recorded_order_value"]
    )
)

check(
    "Monthly delivered value matches",
    close(
        monthly["delivered_order_value"].sum(),
        kpi["delivered_order_value"]
    )
)

check(
    "Status orders match executive",
    int(status["orders"].sum()) ==
    int(kpi["total_orders"])
)

check(
    "Status shares add up to 100%",
    abs(
        number(status["order_share_pct"].sum()) - 100
    ) < 0.1
)


# --------------------------------------------------
# 7. Customer activity
# --------------------------------------------------

print("\n[7] CUSTOMER ACTIVITY")

activity = sql_df("""
    SELECT
        COUNT(*) AS customers,
        COUNT(*) FILTER (
            WHERE days_since_last_order <= 30
        ) AS active_30,
        COUNT(*) FILTER (
            WHERE days_since_last_order > 90
        ) AS inactive_90,
        COUNT(*) FILTER (
            WHERE historical_orders >= 2
        ) AS repeat_customers
    FROM foodpulse.vw_customer_activity
""").iloc[0]

check(
    "20,000 customer activity records",
    int(activity["customers"]) == 20000
)

check(
    "5,260 active in last 30 days",
    int(activity["active_30"]) == 5260
)

check(
    "8,053 inactive for over 90 days",
    int(activity["inactive_90"]) == 8053
)

check(
    "Repeat customers count is valid",
    0 <= int(activity["repeat_customers"]) <= 20000
)

print(
    "       Observed repeat customers:",
    int(activity["repeat_customers"])
)


# --------------------------------------------------
# 8. Stable RFM
# --------------------------------------------------

print("\n[8] STABLE CUSTOMER SEGMENTATION")

rfm_path = (
    ROOT
    / "data/reports/rfm_stability/stable_customer_rfm.csv"
)

if rfm_path.is_file():
    rfm = pd.read_csv(rfm_path)

    check(
        "20,000 stable RFM records",
        len(rfm) == 20000
    )

    if "CustomerID" in rfm.columns:
        check(
            "Unique RFM customer IDs",
            rfm["CustomerID"].nunique() == 20000
        )
    else:
        warning(
            "RFM CustomerID column not found; "
            "uniqueness check skipped."
        )


# --------------------------------------------------
# 9. Recovery candidates
# --------------------------------------------------

print("\n[9] RECOVERY CANDIDATES")

recovery_path = (
    ROOT
    / "data/reports/customer_recovery/"
    "recovery_candidate_ranking.csv"
)

if recovery_path.is_file():
    recovery = pd.read_csv(recovery_path)

    check(
        "2,431 recovery candidates",
        len(recovery) == 2431
    )

    check(
        "Unique recovery customers",
        recovery["CustomerID"].nunique() == len(recovery)
    )

    days = pd.to_numeric(
        recovery["DaysSinceLastOrder"],
        errors="coerce"
    )

    check(
        "All candidates inactive for over 90 days",
        days.gt(90).all()
    )

    delivered = pd.to_numeric(
        recovery["HistoricalDeliveredValue"],
        errors="coerce"
    ).sum()

    check(
        "Historical delivered value reconciles",
        close(delivered, 21076712)
    )

    tiers = (
        recovery["PriorityTier"]
        .astype(str)
        .str.strip()
        .str.lower()
    )

    tier_1 = int(tiers.str.startswith("tier 1").sum())
    tier_2 = int(tiers.str.startswith("tier 2").sum())

    check(
        "Priority 1 = 1,939",
        tier_1 == 1939
    )

    check(
        "Priority 2 = 492",
        tier_2 == 492
    )

    check(
        "All candidates assigned to a known tier",
        tier_1 + tier_2 == len(recovery)
    )


# --------------------------------------------------
# 10. Known limitations
# --------------------------------------------------

print("\n[10] BUSINESS INTERPRETATION WARNINGS")

warning(
    "Recorded order value is not platform revenue."
)

warning(
    "Historical delivered value is not recoverable revenue."
)

warning(
    "September 2025 is incomplete (ends September 26)."
)

warning(
    "Orders before signup affect acquisition analysis."
)

warning(
    "Restaurant quality flags affect named rankings."
)

warning(
    "Scenario simulator uses hypothetical assumptions."
)

warning(
    "Dashboard visual interaction requires manual testing."
)


# --------------------------------------------------
# Final result
# --------------------------------------------------

if engine is not None:
    engine.dispose()

print("\n" + "=" * 65)
print("FINAL QA SUMMARY")
print("=" * 65)

print(f"PASS : {PASS}")
print(f"FAIL : {FAIL}")
print(f"WARN : {WARN}")

if FAIL == 0:
    print("\nRESULT: AUTOMATED QA PASSED")
    print(
        "Next: test Streamlit filters, charts, "
        "navigation and visual layout."
    )
    sys.exit(0)

print("\nRESULT: AUTOMATED QA FAILED")
print("Fix failed checks before final project packaging.")
sys.exit(1)
