from pathlib import Path
import io
import os
import re

import pandas as pd
import psycopg
from psycopg import sql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]

SOURCE = ROOT / "data/processed/orders_analytics_mart.csv"

REPORT_DIR = ROOT / "data/reports/warehouse"
REPORT_DIR.mkdir(parents=True, exist_ok=True)

load_dotenv(ROOT / ".env")

SCHEMA = "foodpulse"
TABLE = "fact_orders_analytics"

EXPECTED_ROWS = 200000
EXPECTED_VALUE = 164914494
EXPECTED_DELIVERED_VALUE = 132092968


def quote_identifier(name):
    return '"' + name.replace('"', '""') + '"'


def sql_type(column, series):
    if column == "OrderID":
        return "BIGINT"

    if pd.api.types.is_bool_dtype(series):
        return "BOOLEAN"

    if pd.api.types.is_integer_dtype(series):
        return "BIGINT"

    if pd.api.types.is_float_dtype(series):
        return "DOUBLE PRECISION"

    if pd.api.types.is_datetime64_any_dtype(series):
        return "TIMESTAMP"

    return "TEXT"


def main():
    print("=" * 65)
    print("FOODPULSE 360 | POSTGRESQL WAREHOUSE LOADER")
    print("=" * 65)

    if not SOURCE.exists():
        raise FileNotFoundError(SOURCE)

    required_env = [
        "PGHOST",
        "PGPORT",
        "PGDATABASE",
        "PGUSER",
        "PGPASSWORD",
    ]

    missing_env = [
        key for key in required_env
        if not os.getenv(key)
    ]

    if missing_env:
        raise RuntimeError(
            f"Missing .env settings: {missing_env}"
        )

    print("\n[1/5] Reading analytics mart...")

    df = pd.read_csv(
        SOURCE,
        low_memory=False
    )

    required_columns = [
        "OrderID",
        "CustomerID",
        "RestaurantID",
        "recorded_order_value",
        "confirmed_delivered_value",
    ]

    missing_columns = [
        column for column in required_columns
        if column not in df.columns
    ]

    if missing_columns:
        raise RuntimeError(
            f"Missing CSV columns: {missing_columns}"
        )

    if len(df) != EXPECTED_ROWS:
        raise AssertionError(
            f"Expected {EXPECTED_ROWS} rows, found {len(df)}"
        )

    if df["OrderID"].isna().any():
        raise AssertionError("Null OrderID detected")

    if not df["OrderID"].is_unique:
        raise AssertionError("Duplicate OrderID detected")

    # Use exact numeric types for financial amounts.
    monetary_columns = [
        "recorded_order_value",
        "confirmed_delivered_value",
    ]

    for column in monetary_columns:
        df[column] = pd.to_numeric(
            df[column],
            errors="raise"
        )

    if not (
        abs(
            df["recorded_order_value"].sum()
            - EXPECTED_VALUE
        ) < 0.01
    ):
        raise AssertionError(
            "Recorded order value mismatch in CSV"
        )

    if not (
        abs(
            df["confirmed_delivered_value"].sum()
            - EXPECTED_DELIVERED_VALUE
        ) < 0.01
    ):
        raise AssertionError(
            "Delivered order value mismatch in CSV"
        )

    # Explicitly normalize boolean columns where present.
    bool_columns = [
        "order_before_signup",
        "signup_cohort_eligible",
        "is_delivered",
        "is_delayed",
        "is_cancelled",
        "restaurant_quality_flag",
        "restaurant_analysis_eligible",
        "customer_cohort_eligible",
        "is_weekend",
    ]

    for column in bool_columns:
        if column not in df.columns:
            continue

        values = (
            df[column]
            .dropna()
            .astype(str)
            .str.lower()
            .unique()
        )

        if not set(values).issubset(
            {"true", "false", "1", "0"}
        ):
            raise ValueError(
                f"Unexpected boolean values in {column}: "
                f"{values}"
            )

        df[column] = (
            df[column]
            .astype("string")
            .str.lower()
            .map({
                "true": True,
                "false": False,
                "1": True,
                "0": False
            })
            .astype("boolean")
        )

    # Convert date-like columns to PostgreSQL dates.
    date_columns = [
        column for column in df.columns
        if (
            column.endswith("_date")
            or column.endswith("_date_clean")
            or column in {
                "customer_signup_date",
                "order_date_clean"
            }
        )
    ]

    for column in date_columns:
        df[column] = pd.to_datetime(
            df[column],
            errors="raise"
        )

    # SQL identifiers must be unique and safe.
    for column in df.columns:
        if not re.fullmatch(
            r"[A-Za-z_][A-Za-z0-9_]*",
            column
        ):
            raise ValueError(
                f"Unsafe column name: {column}"
            )

    print(f"    Rows: {len(df):,}")
    print(f"    Columns: {len(df.columns)}")

    print("\n[2/5] Connecting to PostgreSQL...")

    pg_host = os.getenv("PGHOST")
    pg_port = os.getenv("PGPORT")
    pg_dbname = os.getenv("PGDATABASE")
    pg_user = os.getenv("PGUSER")
    pg_password = os.getenv("PGPASSWORD")

    missing_env_vars = [
        name
        for name, value in {
            "PGHOST": pg_host,
            "PGPORT": pg_port,
            "PGDATABASE": pg_dbname,
            "PGUSER": pg_user,
            "PGPASSWORD": pg_password,
        }.items()
        if value is None
    ]

    if missing_env_vars:
        raise ValueError(
            "Missing PostgreSQL environment variables: "
            + ", ".join(missing_env_vars)
        )

    if pg_port is None:
        raise ValueError("Missing PostgreSQL environment variable: PGPORT")

    connection_kwargs = {
        "host": pg_host,
        "port": int(pg_port),
        "dbname": pg_dbname,
        "user": pg_user,
        "password": pg_password,
    }

    table_name = (
        f"{quote_identifier(SCHEMA)}."
        f"{quote_identifier(TABLE)}"
    )

    column_definitions = []

    for column in df.columns:
        if column in monetary_columns:
            dtype = "NUMERIC(18, 2)"
        else:
            dtype = sql_type(column, df[column])

        definition = (
            f"{quote_identifier(column)} {dtype}"
        )

        if column == "OrderID":
            definition += " PRIMARY KEY"

        column_definitions.append(definition)

    create_sql = (
        f"CREATE TABLE {table_name} (\n"
        + ",\n".join(column_definitions)
        + "\n)"
    )

    with psycopg.connect(**connection_kwargs) as conn:
        with conn.cursor() as cur:

            print("\n[3/5] Creating warehouse table...")

            cur.execute(
                f"CREATE SCHEMA IF NOT EXISTS "
                f"{quote_identifier(SCHEMA)}"
            )

            # Rebuild only this derived table.
            # Does not modify source tables or CSV files.
            cur.execute(
                f"DROP TABLE IF EXISTS {table_name}"
            )

            cur.execute(create_sql)

            print("\n[4/5] Loading 200,000 orders...")

            csv_buffer = io.StringIO()

            df.to_csv(
                csv_buffer,
                index=False,
                header=False,
                na_rep=""
            )

            csv_buffer.seek(0)

            columns_sql = ", ".join(
                quote_identifier(column)
                for column in df.columns
            )

            copy_sql = sql.SQL(
                "COPY {} ({}) FROM STDIN WITH (FORMAT CSV, NULL '')"
            ).format(
                sql.Identifier(SCHEMA, TABLE),
                sql.SQL(", ").join(
                    sql.Identifier(column)
                    for column in df.columns
                ),
            )

            with cur.copy(copy_sql) as copy:
                while True:
                    chunk = csv_buffer.read(1024 * 1024)

                    if not chunk:
                        break

                    copy.write(chunk)

            print("\n[5/5] SQL reconciliation...")

            cur.execute(
                f"""
                SELECT
                    COUNT(*) AS total_orders,
                    COUNT(DISTINCT "OrderID")
                        AS distinct_orders,
                    COUNT(DISTINCT "CustomerID")
                        AS customers,
                    COUNT(DISTINCT "RestaurantID")
                        AS restaurants,
                    SUM("recorded_order_value")
                        AS recorded_value,
                    SUM("confirmed_delivered_value")
                        AS delivered_value
                FROM {table_name}
                """
            )

            result = cur.fetchone()

            if result is None:
                raise RuntimeError(
                    f"Warehouse reconciliation query returned no rows for {table_name}."
                )

            (
                total_orders,
                distinct_orders,
                customers,
                restaurants,
                recorded_value,
                delivered_value
            ) = result

            assert total_orders == EXPECTED_ROWS
            assert distinct_orders == EXPECTED_ROWS
            assert customers == 20000
            assert restaurants == 54600
            assert recorded_value == EXPECTED_VALUE
            assert delivered_value == EXPECTED_DELIVERED_VALUE

            cur.execute(
                f"""
                CREATE INDEX idx_fact_orders_customer
                ON {table_name} ("CustomerID")
                """
            )

            cur.execute(
                f"""
                CREATE INDEX idx_fact_orders_restaurant
                ON {table_name} ("RestaurantID")
                """
            )

            cur.execute(
                f"""
                CREATE INDEX idx_fact_orders_date
                ON {table_name} ("order_date_clean")
                """
            )

            cur.execute(
                f"ANALYZE {table_name}"
            )

    summary = pd.DataFrame([
        ["Total Orders", total_orders],
        ["Distinct Orders", distinct_orders],
        ["Distinct Customers", customers],
        ["Active Restaurants", restaurants],
        ["Recorded Order Value", recorded_value],
        ["Delivered Order Value", delivered_value],
    ], columns=["Metric", "Value"])

    summary.to_csv(
        REPORT_DIR / "warehouse_load_reconciliation.csv",
        index=False
    )

    print("\nWAREHOUSE RECONCILIATION")
    print(summary.to_string(index=False))

    print("\n[PASS] PostgreSQL row counts reconciled.")
    print("[PASS] PostgreSQL financial totals reconciled.")
    print("[PASS] Primary key and indexes created.")
    print("[SUCCESS] Warehouse analytics table ready.")


if __name__ == "__main__":
    main()