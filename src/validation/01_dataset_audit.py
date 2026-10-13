from pathlib import Path
from datetime import datetime
import hashlib
import json
import sys

import numpy as np
import pandas as pd


# ============================================================
# 1. PROJECT CONFIGURATION
# ============================================================

ROOT = Path(__file__).resolve().parents[2]

DATASET = ROOT / "data" / "raw" / "dataset.xlsx"
OUTPUT = ROOT / "data" / "reports" / "phase1"

OUTPUT.mkdir(parents=True, exist_ok=True)

EXPECTED = {
    "Restaurants": 56250,
    "Customers": 20000,
    "Orders": 200000,
    "DateTable": 1000,
}

PRIMARY_KEYS = {
    "Restaurants": "RestaurantID",
    "Customers": "CustomerID",
    "Orders": "OrderID",
    "DateTable": "Date",
}

DATE_COLUMNS = {
    "Customers": ["SignupDate"],
    "Orders": ["OrderDate"],
    "DateTable": ["Date"],
}


# ============================================================
# 2. HELPER FUNCTIONS
# ============================================================

def safe_value(value):
    """Convert pandas/numpy values into JSON-compatible values."""

    if pd.isna(value):
        return None

    if isinstance(value, (pd.Timestamp, datetime)):
        return value.isoformat()

    if isinstance(value, (np.integer,)):
        return int(value)

    if isinstance(value, (np.floating,)):
        return float(value)

    if isinstance(value, (np.bool_,)):
        return bool(value)

    return value


def file_hash(path):
    """Generate SHA256 fingerprint of the source workbook."""

    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024),
            b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def blank_mask(series):
    """
    Detect true nulls and whitespace-only text values.
    Original data is not modified.
    """

    return (
        series.isna()
        | series.astype("string").str.strip().eq("").fillna(False)
    )


def unique_count(series):
    """Count unique nonblank values."""

    return int(series[~blank_mask(series)].nunique())


# ============================================================
# 3. TABLE-LEVEL PROFILING
# ============================================================

def profile_table(sheet_name, df):

    rows, columns = df.shape

    missing_cells = sum(
        int(blank_mask(df[col]).sum())
        for col in df.columns
    )

    total_cells = rows * columns

    duplicate_rows = int(
        df.duplicated(keep="first").sum()
    )

    primary_key = PRIMARY_KEYS[sheet_name]

    key_missing = int(
        blank_mask(df[primary_key]).sum()
    )

    key_duplicates = int(
        df[primary_key].duplicated(keep=False).sum()
    )

    result = {
        "table": sheet_name,
        "rows": rows,
        "columns": columns,
        "total_cells": total_cells,
        "missing_cells": missing_cells,
        "missing_pct": round(
            missing_cells / total_cells * 100, 4
        ) if total_cells else 0,
        "duplicate_rows": duplicate_rows,
        "primary_key": primary_key,
        "missing_key_rows": key_missing,
        "duplicate_key_rows": key_duplicates,
        "unique_keys": unique_count(df[primary_key]),
    }

    return result


# ============================================================
# 4. COLUMN-LEVEL PROFILING
# ============================================================

def profile_columns(sheet_name, df):

    results = []

    for column in df.columns:

        series = df[column]
        missing = blank_mask(series)

        missing_count = int(missing.sum())
        nonmissing_count = int((~missing).sum())

        unique = unique_count(series)

        result = {
            "table": sheet_name,
            "column": column,
            "dtype": str(series.dtype),
            "rows": len(df),
            "missing_count": missing_count,
            "missing_pct": round(
                missing_count / len(df) * 100, 4
            ) if len(df) else 0,
            "nonmissing_count": nonmissing_count,
            "unique_count": unique,
            "unique_pct": round(
                unique / nonmissing_count * 100, 4
            ) if nonmissing_count else 0,
            "sample_value": (
                str(series[~missing].iloc[0])
                if nonmissing_count else None
            ),
        }

        results.append(result)

    return results


# ============================================================
# 5. NUMERIC COLUMN PROFILING
# ============================================================

def profile_numeric(sheet_name, df):

    results = []

    numeric_columns = df.select_dtypes(
        include="number"
    ).columns

    for column in numeric_columns:

        series = pd.to_numeric(
            df[column],
            errors="coerce"
        )

        valid = series.dropna()

        if valid.empty:
            continue

        results.append({
            "table": sheet_name,
            "column": column,
            "count": int(valid.count()),
            "min": float(valid.min()),
            "p01": float(valid.quantile(0.01)),
            "p25": float(valid.quantile(0.25)),
            "median": float(valid.median()),
            "mean": float(valid.mean()),
            "p75": float(valid.quantile(0.75)),
            "p99": float(valid.quantile(0.99)),
            "max": float(valid.max()),
            "std": float(valid.std())
                if len(valid) > 1 else None,
            "zero_count": int((valid == 0).sum()),
            "negative_count": int((valid < 0).sum()),
        })

    return results


# ============================================================
# 6. DATE PROFILING
# ============================================================

def profile_dates(sheet_name, df):

    results = []

    for column in DATE_COLUMNS.get(sheet_name, []):

        original = df[column]

        parsed = pd.to_datetime(
            original,
            errors="coerce"
        )

        invalid = int(
            (
                ~blank_mask(original)
                & parsed.isna()
            ).sum()
        )

        valid = parsed.dropna()

        results.append({
            "table": sheet_name,
            "column": column,
            "valid_dates": int(valid.count()),
            "invalid_dates": invalid,
            "min_date": (
                valid.min().isoformat()
                if not valid.empty else None
            ),
            "max_date": (
                valid.max().isoformat()
                if not valid.empty else None
            ),
            "distinct_dates": int(
                valid.dt.normalize().nunique()
            ),
        })

    return results


# ============================================================
# 7. CATEGORICAL DISTRIBUTIONS
# ============================================================

def profile_categories(sheet_name, df):

    results = []

    for column in df.columns:

        series = df[column]

        if pd.api.types.is_numeric_dtype(series):
            continue

        if column in DATE_COLUMNS.get(sheet_name, []):
            continue

        unique = unique_count(series)

        # Low-cardinality fields only
        if unique > 30:
            continue

        normalized = (
            series.astype("string")
            .str.strip()
            .replace("", pd.NA)
            .fillna("<MISSING>")
        )

        counts = normalized.value_counts(
            dropna=False
        )

        for category, count in counts.items():

            results.append({
                "table": sheet_name,
                "column": column,
                "category": str(category),
                "count": int(count),
                "percentage": round(
                    count / len(df) * 100, 4
                ) if len(df) else 0,
            })

    return results


# ============================================================
# 8. MAIN AUDIT PIPELINE
# ============================================================

def main():

    print("=" * 65)
    print("FOODPULSE 360 - PHASE 1.1 FORENSIC DATA AUDIT")
    print("=" * 65)

    if not DATASET.exists():
        raise FileNotFoundError(
            f"Dataset not found: {DATASET}"
        )

    sha256 = file_hash(DATASET)

    print(f"\nDataset SHA256: {sha256}")

    workbook = pd.ExcelFile(DATASET)

    assert set(workbook.sheet_names) == set(EXPECTED), (
        "Unexpected workbook sheet structure"
    )

    table_results = []
    column_results = []
    numeric_results = []
    date_results = []
    category_results = []

    total_rows = 0

    for sheet_name, expected_rows in EXPECTED.items():

        print(f"\n{'-' * 65}")
        print(f"AUDITING: {sheet_name}")
        print("-" * 65)

        df = pd.read_excel(
            workbook,
            sheet_name=sheet_name
        )

        assert len(df) == expected_rows, (
            f"{sheet_name}: row count mismatch"
        )

        assert df.columns.is_unique, (
            f"{sheet_name}: duplicate column names"
        )

        table = profile_table(sheet_name, df)

        table_results.append(table)

        column_results.extend(
            profile_columns(sheet_name, df)
        )

        numeric_results.extend(
            profile_numeric(sheet_name, df)
        )

        date_results.extend(
            profile_dates(sheet_name, df)
        )

        category_results.extend(
            profile_categories(sheet_name, df)
        )

        total_rows += len(df)

        print(f"Rows: {table['rows']:,}")
        print(f"Columns: {table['columns']}")
        print(f"Missing cells: {table['missing_cells']:,}")
        print(f"Missing %: {table['missing_pct']}%")
        print(f"Exact duplicate rows: {table['duplicate_rows']:,}")
        print(f"Missing PK rows: {table['missing_key_rows']:,}")
        print(f"Duplicate PK rows: {table['duplicate_key_rows']:,}")

    # ========================================================
    # 9. SAVE REPORTS
    # ========================================================

    reports = {
        "table_profile.csv": table_results,
        "column_profile.csv": column_results,
        "numeric_profile.csv": numeric_results,
        "date_profile.csv": date_results,
        "category_profile.csv": category_results,
    }

    for filename, records in reports.items():

        output_path = OUTPUT / filename

        pd.DataFrame(records).to_csv(
            output_path,
            index=False,
            encoding="utf-8-sig"
        )

        print(f"[SAVED] {output_path.name}")

    summary = {
        "project": "FoodPulse 360",
        "phase": "1.1",
        "dataset_sha256": sha256,
        "total_rows": total_rows,
        "table_profiles": table_results,
        "date_profiles": date_results,
        "generated_at": datetime.now().isoformat(),
    }

    with (OUTPUT / "audit_summary.json").open(
        "w",
        encoding="utf-8"
    ) as file:

        json.dump(
            summary,
            file,
            indent=4,
            default=safe_value
        )

    print("\n" + "=" * 65)
    print(f"TOTAL RECORDS AUDITED: {total_rows:,}")
    print("REPORTS GENERATED: 6")
    print("PHASE 1.1 AUDIT EXECUTED SUCCESSFULLY")
    print("=" * 65)


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"\n[FAILED] {type(error).__name__}: {error}")
        sys.exit(1)