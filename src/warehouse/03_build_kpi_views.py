from pathlib import Path
import os
from typing import LiteralString, cast

import psycopg
from psycopg import sql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SCHEMA = "foodpulse"

VIEWS = {
    "vw_executive_kpis": """
        SELECT
            COUNT(*)::BIGINT AS total_orders,
            COUNT(DISTINCT "CustomerID")::BIGINT AS active_customers,
            COUNT(DISTINCT "RestaurantID")::BIGINT AS active_restaurants,

            COALESCE(
                SUM("recorded_order_value"), 0
            ) AS recorded_order_value,

            COALESCE(
                SUM("confirmed_delivered_value"), 0
            ) AS delivered_order_value,

            ROUND(
                AVG("recorded_order_value"), 2
            ) AS average_order_value,

            COUNT(*) FILTER (
                WHERE "is_delivered" IS TRUE
            )::BIGINT AS delivered_orders,

            COUNT(*) FILTER (
                WHERE "is_delayed" IS TRUE
            )::BIGINT AS delayed_orders,

            COUNT(*) FILTER (
                WHERE "is_cancelled" IS TRUE
            )::BIGINT AS cancelled_orders,

            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE "is_cancelled" IS TRUE
                ) / NULLIF(COUNT(*), 0), 2
            ) AS cancellation_rate_pct,

            COUNT(*) FILTER (
                WHERE "order_before_signup" IS TRUE
            )::BIGINT AS chronology_flagged_orders,

            MIN(order_date) AS observation_start,
            MAX(order_date) AS observation_end

        FROM foodpulse.fact_orders
    """,

    "vw_monthly_performance": """
        SELECT
            DATE_TRUNC('month', order_date)::DATE AS order_month,

            COUNT(*)::BIGINT AS orders,

            COUNT(DISTINCT "CustomerID")::BIGINT
                AS active_customers,

            COUNT(DISTINCT "RestaurantID")::BIGINT
                AS active_restaurants,

            SUM("recorded_order_value")
                AS recorded_order_value,

            SUM("confirmed_delivered_value")
                AS delivered_order_value,

            ROUND(
                AVG("recorded_order_value"), 2
            ) AS average_order_value,

            COUNT(*) FILTER (
                WHERE "is_cancelled" IS TRUE
            )::BIGINT AS cancelled_orders,

            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE "is_cancelled" IS TRUE
                ) / NULLIF(COUNT(*), 0), 2
            ) AS cancellation_rate_pct

        FROM foodpulse.fact_orders
        GROUP BY 1
    """,

    "vw_order_status": """
        SELECT
            "order_status_clean" AS order_status,
            COUNT(*)::BIGINT AS orders,
            SUM("recorded_order_value")
                AS recorded_order_value,
            SUM("confirmed_delivered_value")
                AS delivered_order_value,
            ROUND(
                100.0 * COUNT(*)
                / NULLIF(
                    (SELECT COUNT(*)
                     FROM foodpulse.fact_orders), 0
                ), 2
            ) AS order_share_pct

        FROM foodpulse.fact_orders
        GROUP BY 1
    """,

    "vw_customer_activity": """
        SELECT
            "CustomerID",
            COUNT(*)::BIGINT AS historical_orders,
            SUM("recorded_order_value")
                AS historical_recorded_value,
            SUM("confirmed_delivered_value")
                AS historical_delivered_value,
            MIN(order_date) AS first_observed_order,
            MAX(order_date) AS last_observed_order,

            (
                (SELECT MAX(order_date)::DATE
                FROM foodpulse.fact_orders)
                - MAX(order_date)::DATE
            ) AS days_since_last_order

        FROM foodpulse.fact_orders
        GROUP BY "CustomerID"
    """,

    "vw_restaurant_performance": """
        SELECT
            f."RestaurantID",
            r."restaurant_name",
            r."restaurant_location",
            r."restaurant_type",
            r."restaurant_quality_flag",

            COUNT(*)::BIGINT AS orders,

            SUM(f."recorded_order_value")
                AS recorded_order_value,

            SUM(f."confirmed_delivered_value")
                AS delivered_order_value,

            COUNT(*) FILTER (
                WHERE f."is_cancelled" IS TRUE
            )::BIGINT AS cancelled_orders,

            ROUND(
                100.0 * COUNT(*) FILTER (
                    WHERE f."is_cancelled" IS TRUE
                ) / NULLIF(COUNT(*), 0), 2
            ) AS cancellation_rate_pct

        FROM foodpulse.fact_orders f

        JOIN foodpulse.dim_restaurants r
          ON f."RestaurantID" = r."RestaurantID"

        GROUP BY
            f."RestaurantID",
            r."restaurant_name",
            r."restaurant_location",
            r."restaurant_type",
            r."restaurant_quality_flag"
    """
}


def _require_env(name: str) -> str:
    value = os.getenv(name)
    if value is None or value == "":
        raise RuntimeError(f"Missing required environment variable: {name}")
    return value


def _require_int_env(name: str) -> int:
    raw_value = _require_env(name)
    try:
        return int(raw_value)
    except ValueError as exc:
        raise ValueError(
            f"Environment variable {name} must be an integer. "
            f"Received: {raw_value!r}"
        ) from exc


def _fetch_single_row(cur, query_name: str):
    row = cur.fetchone()
    if row is None:
        raise RuntimeError(f"Query returned no rows while validating {query_name}.")
    return row


def main():
    print("=" * 65)
    print("FOODPULSE 360 | SQL KPI VIEWS")
    print("=" * 65)

    connection = {
        "host": _require_env("PGHOST"),
        "port": _require_int_env("PGPORT"),
        "dbname": _require_env("PGDATABASE"),
        "user": _require_env("PGUSER"),
        "password": _require_env("PGPASSWORD"),
    }

    with psycopg.connect(**connection) as conn:
        with conn.cursor() as cur:

            print("\n[1/3] Creating analytical SQL views...")

            for name, query in VIEWS.items():
                query_sql = cast(LiteralString, query)
                cur.execute(
                    sql.SQL("CREATE OR REPLACE VIEW {}.{} AS {}").format(
                        sql.Identifier(SCHEMA),
                        sql.Identifier(name),
                        sql.SQL(query_sql),
                    )
                )
                print(f"    [OK] {SCHEMA}.{name}")

            print("\n[2/3] Validating executive KPIs...")

            cur.execute("""
                SELECT
                    total_orders,
                    active_customers,
                    active_restaurants,
                    recorded_order_value,
                    delivered_order_value,
                    delivered_orders,
                    delayed_orders,
                    cancelled_orders,
                    chronology_flagged_orders
                FROM foodpulse.vw_executive_kpis
            """)

            (
                orders,
                customers,
                restaurants,
                recorded,
                delivered,
                delivered_orders,
                delayed_orders,
                cancelled_orders,
                chronology_flags
            ) = _fetch_single_row(cur, "executive KPI view")

            assert orders == 200000
            assert customers == 20000
            assert restaurants == 54600
            assert recorded == 164914494
            assert delivered == 132092968

            assert delivered_orders == 160227
            assert delayed_orders == 19826
            assert cancelled_orders == 19947

            assert chronology_flags == 18372

            assert (
                delivered_orders
                + delayed_orders
                + cancelled_orders
                == orders
            )

            print("\n[3/3] Cross-validating SQL views...")

            cur.execute("""
                SELECT
                    COUNT(*),
                    SUM(orders),
                    SUM(recorded_order_value),
                    SUM(delivered_order_value)
                FROM foodpulse.vw_monthly_performance
            """)

            (
                months,
                monthly_orders,
                monthly_recorded,
                monthly_delivered
            ) = _fetch_single_row(cur, "monthly performance view")

            assert months == 33
            assert monthly_orders == orders
            assert monthly_recorded == recorded
            assert monthly_delivered == delivered

            cur.execute("""
                SELECT
                    SUM(orders),
                    SUM(recorded_order_value)
                FROM foodpulse.vw_order_status
            """)

            status_orders, status_recorded = _fetch_single_row(
                cur, "order status view"
            )

            assert status_orders == orders
            assert status_recorded == recorded

            cur.execute("""
                SELECT
                    COUNT(*),
                    SUM(historical_orders),
                    SUM(historical_recorded_value)
                FROM foodpulse.vw_customer_activity
            """)

            (
                customer_rows,
                customer_orders,
                customer_recorded
            ) = _fetch_single_row(cur, "customer activity view")

            assert customer_rows == customers
            assert customer_orders == orders
            assert customer_recorded == recorded

            cur.execute("""
                SELECT
                    COUNT(*),
                    SUM(orders),
                    SUM(recorded_order_value)
                FROM foodpulse.vw_restaurant_performance
            """)

            (
                restaurant_rows,
                restaurant_orders,
                restaurant_recorded
            ) = _fetch_single_row(cur, "restaurant performance view")

            assert restaurant_rows == restaurants
            assert restaurant_orders == orders
            assert restaurant_recorded == recorded

    print("\nSQL RECONCILIATION")
    print(f"Total Orders       : {orders:,}")
    print(f"Active Customers   : {customers:,}")
    print(f"Active Restaurants : {restaurants:,}")
    print(f"Monthly Periods    : {months}")
    print(f"Recorded Value     : {recorded:,.2f}")
    print(f"Delivered Value    : {delivered:,.2f}")
    print(f"Cancelled Orders   : {cancelled_orders:,}")
    print(f"Chronology Flags   : {chronology_flags:,}")

    print("\n[PASS] Executive KPI reconciliation.")
    print("[PASS] Monthly and status totals reconciled.")
    print("[PASS] Customer and restaurant views reconciled.")
    print("[SUCCESS] 5 PostgreSQL analytical views ready.")


if __name__ == "__main__":
    main()