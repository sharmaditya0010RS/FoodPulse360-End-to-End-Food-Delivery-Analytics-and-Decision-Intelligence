from pathlib import Path
import hashlib
import sys

import pandas as pd
import sqlalchemy
from sqlalchemy import create_engine, text, URL
from dotenv import load_dotenv
import os


ROOT = Path(__file__).resolve().parent
DATASET = ROOT / "data" / "raw" / "dataset.xlsx"

EXPECTED = {
    "Restaurants": (56250, 14),
    "Customers": (20000, 5),
    "Orders": (200000, 8),
    "DateTable": (1000, 6),
}


def check_python():
    print("\n[1] PYTHON CHECK")

    print("Python:", sys.version.split()[0])
    print("Pandas:", pd.__version__)
    print("SQLAlchemy:", sqlalchemy.__version__)

    assert sys.version_info >= (3, 12), (
        "Python 3.12 or higher required"
    )

    print("[PASS] Python environment")


def check_dataset():
    print("\n[2] DATASET CHECK")

    assert DATASET.exists(), (
        f"Dataset not found: {DATASET}"
    )

    workbook = pd.ExcelFile(DATASET)

    actual_sheets = set(workbook.sheet_names)
    expected_sheets = set(EXPECTED)

    assert actual_sheets == expected_sheets, (
        f"Sheet mismatch: {actual_sheets}"
    )

    total_rows = 0

    for sheet, (expected_rows, expected_cols) in EXPECTED.items():

        df = pd.read_excel(workbook, sheet_name=sheet)

        rows, cols = df.shape

        print(
            f"{sheet}: "
            f"{rows:,} rows | {cols} columns"
        )

        assert rows == expected_rows, (
            f"{sheet}: expected {expected_rows} rows, got {rows}"
        )

        assert cols == expected_cols, (
            f"{sheet}: expected {expected_cols} columns, got {cols}"
        )

        total_rows += rows

    print(f"Total records: {total_rows:,}")

    sha256 = hashlib.sha256()

    with DATASET.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            sha256.update(chunk)

    print("Dataset SHA256:", sha256.hexdigest())

    print("[PASS] Dataset structure")


def check_database():
    print("\n[3] POSTGRESQL CHECK")

    load_dotenv(ROOT / ".env")

    required = [
        "DB_HOST",
        "DB_PORT",
        "DB_NAME",
        "DB_USER",
        "DB_PASSWORD",
    ]

    missing = [key for key in required if not os.getenv(key)]

    assert not missing, (
        f"Missing environment variables: {missing}"
    )

    db_host = os.environ["DB_HOST"]
    db_port = os.environ["DB_PORT"]
    db_name = os.environ["DB_NAME"]
    db_user = os.environ["DB_USER"]
    db_password = os.environ["DB_PASSWORD"]

    url = URL.create(
        drivername="postgresql+psycopg",
        username=db_user,
        password=db_password,
        host=db_host,
        port=int(db_port),
        database=db_name,
    )

    engine = create_engine(
        url,
        pool_pre_ping=True,
        connect_args={"connect_timeout": 5},
    )

    with engine.connect() as connection:

        result = connection.execute(
            text(
                """
                SELECT
                    current_database() AS database,
                    current_user AS username,
                    current_setting('server_version') AS version
                """
            )
        ).mappings().one()

        print("Database:", result["database"])
        print("User:", result["username"])
        print("PostgreSQL:", result["version"])

        assert result["database"] == "foodpulse360"
        assert result["username"] == "foodpulse_user"

        test = connection.execute(
            text("SELECT 1 AS connection_test")
        ).scalar_one()

        assert test == 1

    engine.dispose()

    print("[PASS] PostgreSQL connection")


def main():

    print("=" * 55)
    print("FOODPULSE 360 - PHASE 0 SETUP VALIDATION")
    print("=" * 55)

    checks = [
        check_python,
        check_dataset,
        check_database,
    ]

    passed = 0

    for check in checks:
        try:
            check()
            passed += 1

        except Exception as error:
            print(f"[FAIL] {check.__name__}")
            print(f"Reason: {error}")

    print("\n" + "=" * 55)
    print(f"FINAL RESULT: {passed}/{len(checks)} checks passed")

    if passed == len(checks):
        print("PHASE 0 SETUP VALIDATED")
    else:
        print("FIX FAILED CHECKS BEFORE PHASE 1")

    print("=" * 55)

    return passed == len(checks)


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)