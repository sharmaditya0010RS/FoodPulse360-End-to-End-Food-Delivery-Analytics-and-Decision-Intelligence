from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/processed"
REPORTS = ROOT / "data/reports/cleaning"

OUTPUT.mkdir(parents=True, exist_ok=True)
REPORTS.mkdir(parents=True, exist_ok=True)

df = pd.read_excel(SOURCE, sheet_name="Restaurants")
raw = df.copy(deep=True)

def text_clean(series):
    return series.astype("string").str.strip()

def blank(series):
    s = text_clean(series)
    return s.isna() | s.eq("").fillna(False)

# --------------------------------------------------
# 1. Preserve raw data and create clean columns
# --------------------------------------------------

df["online_order_clean"] = text_clean(df["online_order"])
df["book_table_clean"] = text_clean(df["book_table"])

df.loc[
    ~df["online_order_clean"].isin(["Yes", "No"]).fillna(False),
    "online_order_clean"
] = pd.NA

df.loc[
    ~df["book_table_clean"].isin(["Yes", "No"]).fillna(False),
    "book_table_clean"
] = pd.NA

# --------------------------------------------------
# 2. Strict numeric parsing
# --------------------------------------------------

df["votes_clean"] = pd.to_numeric(
    df["votes"],
    errors="coerce"
)

cost_text = text_clean(
    df["approx_cost(for two people)"]
).str.replace(",", "", regex=False)

df["cost_for_two_clean"] = pd.to_numeric(
    cost_text,
    errors="coerce"
)

rate_text = text_clean(df["rate"])

df["rating_clean"] = pd.to_numeric(
    rate_text.str.extract(
        r"^(\d+(?:\.\d+)?)(?:\s*/\s*5)?$"
    )[0],
    errors="coerce"
)

# Enforce sensible numeric ranges
df.loc[
    ~df["rating_clean"].between(0, 5),
    "rating_clean"
] = np.nan

df.loc[
    df["votes_clean"] < 0,
    "votes_clean"
] = np.nan

df.loc[
    df["cost_for_two_clean"] <= 0,
    "cost_for_two_clean"
] = np.nan

# --------------------------------------------------
# 3. Detect suspected contamination
# --------------------------------------------------

flags = pd.DataFrame(index=df.index)

flags["invalid_online_order"] = (
    ~blank(raw["online_order"])
    & df["online_order_clean"].isna()
)

flags["invalid_book_table"] = (
    ~blank(raw["book_table"])
    & df["book_table_clean"].isna()
)

flags["invalid_votes"] = (
    ~blank(raw["votes"])
    & df["votes_clean"].isna()
)

flags["invalid_cost"] = (
    ~blank(raw["approx_cost(for two people)"])
    & df["cost_for_two_clean"].isna()
)

flags["invalid_rating"] = (
    ~blank(raw["rate"])
    & df["rating_clean"].isna()
    & ~rate_text.str.upper().isin(["NEW", "-"]).fillna(False)
)

flags = flags.fillna(False)

df["quality_issue_count"] = flags.sum(axis=1)
df["suspected_contamination"] = (
    df["quality_issue_count"] > 0
)

for col in flags.columns:
    df[col] = flags[col]

# --------------------------------------------------
# 4. Safe text cleaning
# --------------------------------------------------

for col in [
    "name",
    "address",
    "location",
    "rest_type",
    "cuisines",
    "listed_in(type)",
    "listed_in(city)"
]:
    df[col + "_clean"] = text_clean(df[col])

    df.loc[
        blank(df[col]),
        col + "_clean"
    ] = pd.NA

# IMPORTANT:
# Text columns are NOT automatically trusted.
# Suspected rows remain flagged for downstream filtering.

# --------------------------------------------------
# 5. Independent validation
# --------------------------------------------------

assert len(df) == 56250
assert df["RestaurantID"].is_unique
assert df["RestaurantID"].notna().all()

assert int(df["suspected_contamination"].sum()) == 4519

assert int(
    (df["quality_issue_count"] >= 2).sum()
) == 4480

assert df["rating_clean"].dropna().between(0, 5).all()

assert df["votes_clean"].dropna().ge(0).all()

assert df["cost_for_two_clean"].dropna().gt(0).all()

assert set(
    df["online_order_clean"].dropna().unique()
).issubset({"Yes", "No"})

assert set(
    df["book_table_clean"].dropna().unique()
).issubset({"Yes", "No"})

# Check original columns remain unchanged
for col in raw.columns:
    assert df[col].equals(raw[col]), (
        f"Raw column modified: {col}"
    )

# --------------------------------------------------
# 6. Quality summary
# --------------------------------------------------

summary = pd.DataFrame([
    ["Total Restaurants", len(df)],
    [
        "Suspected Contaminated",
        int(df["suspected_contamination"].sum())
    ],
    [
        "Multiple Quality Issues",
        int((df["quality_issue_count"] >= 2).sum())
    ],
    [
        "Valid Online Order Values",
        int(df["online_order_clean"].notna().sum())
    ],
    [
        "Valid Book Table Values",
        int(df["book_table_clean"].notna().sum())
    ],
    [
        "Valid Numeric Ratings",
        int(df["rating_clean"].notna().sum())
    ],
    [
        "Valid Numeric Votes",
        int(df["votes_clean"].notna().sum())
    ],
    [
        "Valid Cost For Two",
        int(df["cost_for_two_clean"].notna().sum())
    ],
], columns=["Metric", "Value"])

# --------------------------------------------------
# 7. Export
# --------------------------------------------------

df.to_csv(
    OUTPUT / "restaurants_clean.csv",
    index=False,
    encoding="utf-8-sig"
)

summary.to_csv(
    REPORTS / "restaurant_cleaning_summary.csv",
    index=False,
    encoding="utf-8-sig"
)

print("=" * 65)
print("FOODPULSE 360 | RESTAURANT CLEANING PIPELINE")
print("=" * 65)

print("\n", summary.to_string(index=False))

print("\n[PASS] Original columns preserved.")
print("[PASS] Restaurant count and keys preserved.")
print("[PASS] Quality flags reconciled.")
print("[PASS] Cleaned numeric ranges validated.")
print("[SUCCESS] restaurants_clean.csv generated.")