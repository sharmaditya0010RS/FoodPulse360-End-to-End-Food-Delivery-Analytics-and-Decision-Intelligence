from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/reports/contamination_impact"
OUTPUT.mkdir(parents=True, exist_ok=True)

restaurants = pd.read_excel(SOURCE, sheet_name="Restaurants")
orders = pd.read_excel(
    SOURCE,
    sheet_name="Orders",
    usecols=["OrderID", "RestaurantID", "OrderValue", "OrderStatus"]
)

# --------------------------------------------------
# 1. Strict validation rules
# --------------------------------------------------

def clean_text(series):
    return series.astype("string").str.strip()

def blank(series):
    s = clean_text(series)
    return s.isna() | s.eq("").fillna(False)

online = clean_text(restaurants["online_order"])
booking = clean_text(restaurants["book_table"])

votes = pd.to_numeric(restaurants["votes"], errors="coerce")

cost = pd.to_numeric(
    clean_text(restaurants["approx_cost(for two people)"])
    .str.replace(",", "", regex=False),
    errors="coerce"
)

rate_text = clean_text(restaurants["rate"])

rating = pd.to_numeric(
    rate_text.str.extract(
        r"^(\d+(?:\.\d+)?)(?:\s*/\s*5)?$"
    )[0],
    errors="coerce"
)

# --------------------------------------------------
# 2. Contamination flags
# --------------------------------------------------

flags = pd.DataFrame({
    "RestaurantID": restaurants["RestaurantID"],

    "InvalidOnlineOrder": (
        ~blank(restaurants["online_order"])
        & ~online.isin(["Yes", "No"])
    ),

    "InvalidBookTable": (
        ~blank(restaurants["book_table"])
        & ~booking.isin(["Yes", "No"])
    ),

    "InvalidVotes": (
        ~blank(restaurants["votes"])
        & votes.isna()
    ),

    "InvalidCost": (
        ~blank(restaurants["approx_cost(for two people)"])
        & cost.isna()
    ),

    "InvalidRating": (
        ~blank(restaurants["rate"])
        & rating.isna()
        & ~rate_text.str.upper().isin(["NEW", "-"])
    ),
})

flag_columns = [
    c for c in flags.columns if c != "RestaurantID"
]

flags[flag_columns] = flags[flag_columns].fillna(False)

flags["IssueCount"] = flags[flag_columns].sum(axis=1)

flags["SuspectedContamination"] = flags["IssueCount"] > 0

# --------------------------------------------------
# 3. Restaurant-level impact
# --------------------------------------------------

affected = flags.loc[
    flags["SuspectedContamination"]
].copy()

summary_rows = [
    ["Total Restaurants", len(restaurants)],
    ["Suspected Contaminated Restaurants", len(affected)],
    ["Affected Restaurant Percentage",
     round(len(affected) / len(restaurants) * 100, 2)],
    ["Restaurants With Multiple Issues",
     int((flags["IssueCount"] >= 2).sum())],
]

for col in flag_columns:
    summary_rows.append([col, int(flags[col].sum())])

# --------------------------------------------------
# 4. Order-level impact
# --------------------------------------------------

orders["OrderValue"] = pd.to_numeric(
    orders["OrderValue"], errors="raise"
)

joined = orders.merge(
    flags[["RestaurantID", "SuspectedContamination", "IssueCount"]],
    on="RestaurantID",
    how="left",
    validate="many_to_one"
)

assert joined["SuspectedContamination"].notna().all()

affected_orders = joined.loc[
    joined["SuspectedContamination"]
].copy()

summary_rows.extend([
    ["Total Orders", len(orders)],
    ["Orders Linked To Suspected Restaurants", len(affected_orders)],
    ["Affected Order Percentage",
     round(len(affected_orders) / len(orders) * 100, 2)],
    ["Recorded Value Linked To Suspected Restaurants",
     affected_orders["OrderValue"].sum()],
])

summary = pd.DataFrame(
    summary_rows,
    columns=["Metric", "Value"]
)

# --------------------------------------------------
# 5. Status-level impact
# --------------------------------------------------

status_impact = (
    joined.groupby(
        ["SuspectedContamination", "OrderStatus"],
        dropna=False
    )
    .agg(
        Orders=("OrderID", "count"),
        RecordedOrderValue=("OrderValue", "sum")
    )
    .reset_index()
)

# --------------------------------------------------
# 6. Evidence samples
# --------------------------------------------------

sample_columns = [
    "RestaurantID",
    "name",
    "online_order",
    "book_table",
    "rate",
    "votes",
    "approx_cost(for two people)",
    "location",
    "rest_type",
    "cuisines",
]

samples = restaurants.loc[
    flags["SuspectedContamination"],
    sample_columns
].head(100)

# --------------------------------------------------
# 7. Independent reconciliation
# --------------------------------------------------

assert len(flags) == len(restaurants)
assert len(joined) == len(orders)

assert (
    len(affected)
    + int((~flags["SuspectedContamination"]).sum())
    == len(restaurants)
)

assert status_impact["Orders"].sum() == len(orders)

assert abs(
    status_impact["RecordedOrderValue"].sum()
    - orders["OrderValue"].sum()
) < 0.01

# --------------------------------------------------
# 8. Save reports
# --------------------------------------------------

reports = {
    "contamination_summary.csv": summary,
    "restaurant_contamination_flags.csv": flags,
    "affected_orders.csv": affected_orders,
    "status_impact.csv": status_impact,
    "contaminated_samples.csv": samples,
}

for name, report in reports.items():
    report.to_csv(
        OUTPUT / name,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 65)
print("FOODPULSE 360 | CONTAMINATION IMPACT AUDIT")
print("=" * 65)

print("\nSUMMARY")
print(summary.to_string(index=False))

print("\nSTATUS IMPACT")
print(status_impact.to_string(index=False))

print("\n[PASS] Restaurant counts reconciled.")
print("[PASS] Order counts reconciled.")
print("[PASS] Recorded order values reconciled.")
print("[SUCCESS] 5 evidence reports saved.")