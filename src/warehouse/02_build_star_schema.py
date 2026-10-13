from pathlib import Path
import os

import psycopg
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / ".env")

SCHEMA = "foodpulse"
SOURCE = f"{SCHEMA}.fact_orders_analytics"

EXPECTED_ORDERS = 200000
EXPECTED_CUSTOMERS = 20000
EXPECTED_ACTIVE_RESTAURANTS = 54600
EXPECTED_RECORDED_VALUE = 164914494
EXPECTED_DELIVERED_VALUE = 132092968


def fetch_one_row(cur):
    row = cur.fetchone()
    if row is None:
        raise RuntimeError("Expected a row from the database query, but received None.")
    return row


def main():
    print("=" * 65)
    print("FOODPULSE 360 | STAR SCHEMA BUILDER")
    print("=" * 65)

    connection = {
        "host": os.getenv("PGHOST") or "localhost",
        "port": int(os.getenv("PGPORT") or 5432),
        "dbname": os.getenv("PGDATABASE") or "postgres",
        "user": os.getenv("PGUSER") or "postgres",
        "password": os.getenv("PGPASSWORD") or "",
    }

    with psycopg.connect(**connection) as conn:
        with conn.cursor() as cur:

            print("\n[1/6] Validating source table...")

            cur.execute(f"""
                SELECT
                    COUNT(*),
                    COUNT(DISTINCT "OrderID")
                FROM {SOURCE}
            """)

            rows, distinct_orders = fetch_one_row(cur)

            assert rows == EXPECTED_ORDERS
            assert distinct_orders == EXPECTED_ORDERS

            print("\n[2/6] Creating customer dimension...")

            cur.execute(f"""
                DROP TABLE IF EXISTS {SCHEMA}.fact_orders;
                DROP TABLE IF EXISTS {SCHEMA}.dim_customers;
                DROP TABLE IF EXISTS {SCHEMA}.dim_restaurants;
                DROP TABLE IF EXISTS {SCHEMA}.dim_dates;
            """)

            cur.execute(f"""
                CREATE TABLE {SCHEMA}.dim_customers AS
                SELECT DISTINCT ON ("CustomerID")
                    "CustomerID",
                    "customer_city",
                    "customer_type",
                    "customer_signup_date"
                FROM {SOURCE}
                ORDER BY "CustomerID", "OrderID";

                ALTER TABLE {SCHEMA}.dim_customers
                ADD PRIMARY KEY ("CustomerID");
            """)

            print("\n[3/6] Creating restaurant dimension...")

            cur.execute(f"""
                CREATE TABLE {SCHEMA}.dim_restaurants AS
                SELECT DISTINCT ON ("RestaurantID")
                    "RestaurantID",
                    "restaurant_name",
                    "restaurant_location",
                    "restaurant_type",
                    "restaurant_cuisines",
                    "restaurant_rating",
                    "restaurant_votes",
                    "restaurant_cost_for_two",
                    "restaurant_quality_flag",
                    "restaurant_analysis_eligible"
                FROM {SOURCE}
                ORDER BY "RestaurantID", "OrderID";

                ALTER TABLE {SCHEMA}.dim_restaurants
                ADD PRIMARY KEY ("RestaurantID");
            """)

            print("\n[4/6] Creating date dimension...")

            cur.execute(f"""
                CREATE TABLE {SCHEMA}.dim_dates AS
                SELECT DISTINCT ON ("order_date_clean")
                    "order_date_clean" AS order_date,
                    "order_year",
                    "order_month",
                    "order_month_name",
                    "order_quarter",
                    "order_day_name",
                    "is_weekend"
                FROM {SOURCE}
                ORDER BY "order_date_clean", "OrderID";

                ALTER TABLE {SCHEMA}.dim_dates
                ADD PRIMARY KEY (order_date);
            """)

            print("\n[5/6] Creating order fact table...")

            cur.execute(f"""
                CREATE TABLE {SCHEMA}.fact_orders AS
                SELECT
                    "OrderID",
                    "CustomerID",
                    "RestaurantID",
                    "order_date_clean" AS order_date,
                    "order_value_clean",
                    "recorded_order_value",
                    "confirmed_delivered_value",
                    "order_status_clean",
                    "quantity_clean",
                    "delivery_mins_clean",
                    "order_before_signup",
                    "signup_cohort_eligible",
                    "is_delivered",
                    "is_delayed",
                    "is_cancelled"
                FROM {SOURCE};

                ALTER TABLE {SCHEMA}.fact_orders
                ADD PRIMARY KEY ("OrderID");

                ALTER TABLE {SCHEMA}.fact_orders
                ADD CONSTRAINT fk_orders_customers
                FOREIGN KEY ("CustomerID")
                REFERENCES {SCHEMA}.dim_customers("CustomerID");

                ALTER TABLE {SCHEMA}.fact_orders
                ADD CONSTRAINT fk_orders_restaurants
                FOREIGN KEY ("RestaurantID")
                REFERENCES {SCHEMA}.dim_restaurants("RestaurantID");

                ALTER TABLE {SCHEMA}.fact_orders
                ADD CONSTRAINT fk_orders_dates
                FOREIGN KEY (order_date)
                REFERENCES {SCHEMA}.dim_dates(order_date);

                CREATE INDEX idx_star_customer
                ON {SCHEMA}.fact_orders("CustomerID");

                CREATE INDEX idx_star_restaurant
                ON {SCHEMA}.fact_orders("RestaurantID");

                CREATE INDEX idx_star_date
                ON {SCHEMA}.fact_orders(order_date);
            """)

            print("\n[6/6] Reconciling star schema...")

            cur.execute(f"""
                SELECT
                    COUNT(*),
                    COUNT(DISTINCT "OrderID"),
                    SUM("recorded_order_value"),
                    SUM("confirmed_delivered_value")
                FROM {SCHEMA}.fact_orders
            """)

            (
                fact_rows,
                unique_orders,
                recorded_value,
                delivered_value
            ) = fetch_one_row(cur)

            cur.execute(
                f"SELECT COUNT(*) FROM {SCHEMA}.dim_customers"
            )
            customer_rows = fetch_one_row(cur)[0]

            cur.execute(
                f"SELECT COUNT(*) FROM {SCHEMA}.dim_restaurants"
            )
            restaurant_rows = fetch_one_row(cur)[0]

            cur.execute(
                f"SELECT COUNT(*) FROM {SCHEMA}.dim_dates"
            )
            date_rows = fetch_one_row(cur)[0]

            assert fact_rows == EXPECTED_ORDERS
            assert unique_orders == EXPECTED_ORDERS
            assert customer_rows == EXPECTED_CUSTOMERS
            assert restaurant_rows == EXPECTED_ACTIVE_RESTAURANTS
            assert recorded_value == EXPECTED_RECORDED_VALUE
            assert delivered_value == EXPECTED_DELIVERED_VALUE

            # Date dimension is built from observed order dates,
            # so count can be less than the full 1,000-day calendar.
            assert 1 <= date_rows <= 1000

            print("\nSTAR SCHEMA RECONCILIATION")
            print(f"Fact Orders       : {fact_rows:,}")
            print(f"Dim Customers     : {customer_rows:,}")
            print(f"Dim Restaurants   : {restaurant_rows:,}")
            print(f"Dim Dates         : {date_rows:,}")
            print(f"Recorded Value    : {recorded_value:,.2f}")
            print(f"Delivered Value   : {delivered_value:,.2f}")

            print("\n[PASS] Fact totals reconciled.")
            print("[PASS] Dimension keys validated.")
            print("[PASS] Foreign key constraints created.")
            print("[SUCCESS] PostgreSQL star schema ready.")


if __name__ == "__main__":
    main()