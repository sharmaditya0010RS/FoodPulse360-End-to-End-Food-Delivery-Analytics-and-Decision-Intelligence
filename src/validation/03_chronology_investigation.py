from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/reports/chronology"
OUTPUT.mkdir(parents=True, exist_ok=True)

orders = pd.read_excel(
    SOURCE,
    sheet_name="Orders",
    usecols=[
        "OrderID", "CustomerID",
        "OrderDate", "OrderValue", "OrderStatus"
    ]
)

customers = pd.read_excel(
    SOURCE,
    sheet_name="Customers",
    usecols=["CustomerID", "SignupDate", "CustomerType"]
)

orders["OrderDate"] = pd.to_datetime(
    orders["OrderDate"], errors="coerce"
).dt.normalize()

customers["SignupDate"] = pd.to_datetime(
    customers["SignupDate"], errors="coerce"
).dt.normalize()

df = orders.merge(
    customers,
    on="CustomerID",
    how="left",
    validate="many_to_one"
)

df["DaysBeforeSignup"] = (
    df["SignupDate"] - df["OrderDate"]
).dt.days

invalid = df.loc[
    df["DaysBeforeSignup"] > 0
].copy()

# 1. Customer-level impact
affected_customers = invalid["CustomerID"].nunique()

# 2. Chronology severity
severity = pd.cut(
    invalid["DaysBeforeSignup"],
    bins=[0, 7, 30, 90, 365, float("inf")],
    labels=[
        "1-7 days",
        "8-30 days",
        "31-90 days",
        "91-365 days",
        "Over 365 days"
    ]
)

severity_report = (
    severity.value_counts()
    .reindex(severity.cat.categories, fill_value=0)
    .rename_axis("Severity")
    .reset_index(name="Orders")
)

severity_report["Percentage"] = (
    severity_report["Orders"]
    / len(invalid) * 100
).round(2)

# 3. Status distribution
status_report = (
    invalid.groupby("OrderStatus", dropna=False)
    .agg(
        Orders=("OrderID", "count"),
        OrderValue=("OrderValue", "sum")
    )
    .reset_index()
)

# 4. Monthly trend
invalid["OrderMonth"] = (
    invalid["OrderDate"].dt.to_period("M").astype(str)
)

monthly_report = (
    invalid.groupby("OrderMonth")
    .agg(
        InvalidOrders=("OrderID", "count"),
        AffectedCustomers=("CustomerID", "nunique")
    )
    .reset_index()
)

# 5. Summary
summary = pd.DataFrame([
    ["Total Orders", len(df)],
    ["Orders Before Signup", len(invalid)],
    ["Invalid Order Percentage", round(len(invalid) / len(df) * 100, 2)],
    ["Affected Customers", affected_customers],
    ["Affected Customer Percentage",
     round(affected_customers / len(customers) * 100, 2)],
    ["Minimum Days Before Signup", invalid["DaysBeforeSignup"].min()],
    ["Median Days Before Signup", invalid["DaysBeforeSignup"].median()],
    ["Maximum Days Before Signup", invalid["DaysBeforeSignup"].max()],
    ["Associated Order Value", invalid["OrderValue"].sum()],
], columns=["Metric", "Value"])

# 6. Cross-validation
assert len(invalid) == int(
    (df["OrderDate"] < df["SignupDate"]).sum()
)

assert len(invalid) <= len(df)
assert affected_customers <= len(customers)
assert severity_report["Orders"].sum() == len(invalid)
assert status_report["Orders"].sum() == len(invalid)

# 7. Save evidence
reports = {
    "chronology_summary.csv": summary,
    "chronology_severity.csv": severity_report,
    "chronology_status.csv": status_report,
    "chronology_monthly.csv": monthly_report,
    "chronology_invalid_orders.csv": invalid,
}

for filename, report in reports.items():
    report.to_csv(
        OUTPUT / filename,
        index=False,
        encoding="utf-8-sig"
    )

print("=" * 60)
print("FOODPULSE 360 | CHRONOLOGY INVESTIGATION")
print("=" * 60)

print("\nSUMMARY")
print(summary.to_string(index=False))

print("\nSEVERITY")
print(severity_report.to_string(index=False))

print("\nORDER STATUS")
print(status_report.to_string(index=False))

print("\n[SUCCESS] 5 evidence reports generated.")
print("[SUCCESS] Cross-validation passed.")