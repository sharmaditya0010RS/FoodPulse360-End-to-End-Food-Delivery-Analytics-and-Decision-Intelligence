from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/reports/restaurant_diagnostics"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_excel(SOURCE, sheet_name="Restaurants")

def blank_mask(s):
    return (
        s.isna()
        | s.astype("string").str.strip().eq("").fillna(False)
    )

def diagnose(column, cleaned):
    raw = df[column]
    blank = blank_mask(raw)
    invalid = ~blank & cleaned.isna()

    examples = (
        raw[invalid]
        .astype("string")
        .value_counts()
        .head(15)
        .reset_index()
    )
    examples.columns = ["RawValue", "Count"]
    examples.insert(0, "Column", column)

    return {
        "Column": column,
        "Total": len(df),
        "Blank": int(blank.sum()),
        "UnparseableNonBlank": int(invalid.sum()),
        "Parsed": int(cleaned.notna().sum()),
    }, examples

# Strict parsing: no guessing or automatic imputation
votes = pd.to_numeric(df["votes"], errors="coerce")

cost = pd.to_numeric(
    df["approx_cost(for two people)"]
    .astype("string")
    .str.replace(",", "", regex=False)
    .str.strip(),
    errors="coerce"
)

rate_text = df["rate"].astype("string").str.strip()

# Supports "4.2" and "4.2/5"; rejects other formats
rate_clean = pd.to_numeric(
    rate_text.str.extract(
        r"^(\d+(?:\.\d+)?)(?:\s*/\s*5)?$"
    )[0],
    errors="coerce"
)

results = []
examples = []

for col, parsed in [
    ("votes", votes),
    ("approx_cost(for two people)", cost),
    ("rate", rate_clean),
]:
    summary, sample = diagnose(col, parsed)
    results.append(summary)
    examples.append(sample)

summary = pd.DataFrame(results)
invalid_examples = pd.concat(examples, ignore_index=True)

# Rating range checks
rating_outliers = df.loc[
    rate_clean.notna() & ~rate_clean.between(0, 5),
    ["RestaurantID", "name", "rate"]
].copy()

# Inspect suspicious high-cardinality categorical fields
category_cols = [
    "online_order",
    "book_table",
    "listed_in(type)",
    "listed_in(city)",
    "rest_type",
    "location",
]

category_summary = pd.DataFrame([
    {
        "Column": col,
        "DistinctNonBlank": int(
            df.loc[~blank_mask(df[col]), col].nunique()
        ),
        "Blank": int(blank_mask(df[col]).sum()),
        "Top5Values": str(
            df[col].value_counts().head(5).to_dict()
        ),
    }
    for col in category_cols
])

# Row-level examples of unparseable values
invalid_rows = []

for col, parsed in [
    ("votes", votes),
    ("approx_cost(for two people)", cost),
    ("rate", rate_clean),
]:
    mask = ~blank_mask(df[col]) & parsed.isna()
    subset = df.loc[
        mask, ["RestaurantID", "name", col]
    ].copy()
    subset["ProblemColumn"] = col
    subset["RawValue"] = subset[col].astype("string")
    invalid_rows.append(
        subset[
            ["RestaurantID", "name", "ProblemColumn", "RawValue"]
        ]
    )

invalid_records = pd.concat(invalid_rows, ignore_index=True)

# Proof checks
assert len(df) == 56250
assert (
    summary["Blank"]
    + summary["UnparseableNonBlank"]
    + summary["Parsed"]
).eq(summary["Total"]).all()

assert len(rating_outliers) == int(
    (rate_clean.notna() & ~rate_clean.between(0, 5)).sum()
)

reports = {
    "parseability_summary.csv": summary,
    "invalid_value_examples.csv": invalid_examples,
    "invalid_value_records.csv": invalid_records,
    "rating_outliers.csv": rating_outliers,
    "category_diagnostics.csv": category_summary,
}

for name, report in reports.items():
    report.to_csv(
        OUTPUT / name,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | RESTAURANT VALUE DIAGNOSTICS")
print("=" * 65)

print("\nPARSEABILITY SUMMARY")
print(summary.to_string(index=False))

print("\nTOP INVALID VALUE EXAMPLES")
print(invalid_examples.to_string(index=False))

print("\nRATING OUTLIERS")
print(rating_outliers.to_string(index=False))

print("\nCATEGORY DIAGNOSTICS")
print(category_summary.to_string(index=False))

print("\n[PASS] Parseability counts reconciled.")
print("[SUCCESS] 5 diagnostic reports saved.")