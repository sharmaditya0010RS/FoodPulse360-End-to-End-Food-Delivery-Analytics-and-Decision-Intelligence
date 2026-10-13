from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/reports/date_quality"
OUTPUT.mkdir(parents=True, exist_ok=True)

df = pd.read_excel(SOURCE, sheet_name="DateTable")

df["Date"] = pd.to_datetime(df["Date"], errors="coerce")

df["ExpectedMonthName"] = df["Date"].dt.month_name()
df["ExpectedMonthShort"] = df["Date"].dt.strftime("%b")

actual = df["MonthName"].astype("string").str.strip().str.casefold()

full_match = actual.eq(
    df["ExpectedMonthName"].str.casefold()
).fillna(False)

short_match = actual.eq(
    df["ExpectedMonthShort"].str.casefold()
).fillna(False)

df["FullNameMatch"] = full_match
df["ShortNameMatch"] = short_match

df["RecognizedFormat"] = (
    full_match | short_match
)

df["UnrecognizedMonthName"] = (
    ~df["RecognizedFormat"]
)

# Check numeric month consistency independently
df["MonthNumberCorrect"] = (
    pd.to_numeric(df["MonthNo"], errors="coerce")
    == df["Date"].dt.month
).fillna(False)

summary = pd.DataFrame([
    ["Total Dates", len(df)],
    ["Full Month Name Matches", int(full_match.sum())],
    ["Abbreviated Month Matches", int(short_match.sum())],
    ["Recognized Month Formats", int(df["RecognizedFormat"].sum())],
    ["Unrecognized Month Names", int(df["UnrecognizedMonthName"].sum())],
    ["Correct Month Numbers", int(df["MonthNumberCorrect"].sum())],
], columns=["Metric", "Value"])

format_examples = (
    df.groupby(
        ["MonthName", "ExpectedMonthName"],
        dropna=False
    )
    .size()
    .reset_index(name="Rows")
    .sort_values("Rows", ascending=False)
)

unrecognized = df.loc[
    df["UnrecognizedMonthName"],
    ["Date", "MonthNo", "MonthName", "ExpectedMonthName"]
]

assert len(df) == 1000

assert (
    int(df["RecognizedFormat"].sum())
    + int(df["UnrecognizedMonthName"].sum())
    == 1000
)

assert int(df["MonthNumberCorrect"].sum()) == 1000

summary.to_csv(
    OUTPUT / "month_name_diagnostics.csv",
    index=False
)

format_examples.to_csv(
    OUTPUT / "month_name_format_examples.csv",
    index=False
)

unrecognized.to_csv(
    OUTPUT / "unrecognized_month_names.csv",
    index=False
)

print("=" * 65)
print("FOODPULSE 360 | MONTH NAME DIAGNOSTICS")
print("=" * 65)

print("\nSUMMARY")
print(summary.to_string(index=False))

print("\nTOP MONTH NAME PATTERNS")
print(format_examples.head(20).to_string(index=False))

print("\n[PASS] Month format counts reconciled.")
print("[PASS] Month numbers match actual dates.")
print("[SUCCESS] 3 diagnostic reports saved.")