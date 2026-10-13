from pathlib import Path
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "data/raw/dataset.xlsx"
OUTPUT = ROOT / "data/reports/relationships"
OUTPUT.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("FOODPULSE 360 | RELATIONSHIP VALIDATION")
print("=" * 60)

orders = pd.read_excel(
    SOURCE,
    sheet_name="Orders",
    usecols=["OrderID", "RestaurantID", "CustomerID", "OrderDate"]
)

restaurants = pd.read_excel(
    SOURCE,
    sheet_name="Restaurants",
    usecols=["RestaurantID"]
)

customers = pd.read_excel(
    SOURCE,
    sheet_name="Customers",
    usecols=["CustomerID", "SignupDate"]
)

dates = pd.read_excel(
    SOURCE,
    sheet_name="DateTable",
    usecols=["Date"]
)

# ---------------------------------------------------
# 1. Validate unique dimension keys
# ---------------------------------------------------

assert restaurants["RestaurantID"].is_unique
assert customers["CustomerID"].is_unique
assert orders["OrderID"].is_unique
assert dates["Date"].is_unique

# ---------------------------------------------------
# 2. Validate restaurant references
# ---------------------------------------------------

restaurant_valid = orders["RestaurantID"].isin(
    restaurants["RestaurantID"]
)

restaurant_orphans = orders.loc[
    ~restaurant_valid
].copy()

# ---------------------------------------------------
# 3. Validate customer references
# ---------------------------------------------------

customer_valid = orders["CustomerID"].isin(
    customers["CustomerID"]
)

customer_orphans = orders.loc[
    ~customer_valid
].copy()

# ---------------------------------------------------
# 4. Validate date references
# ---------------------------------------------------

orders["OrderDate"] = pd.to_datetime(
    orders["OrderDate"], errors="coerce"
).dt.normalize()

dates["Date"] = pd.to_datetime(
    dates["Date"], errors="coerce"
).dt.normalize()

date_valid = orders["OrderDate"].isin(dates["Date"])

date_orphans = orders.loc[
    ~date_valid
].copy()

# ---------------------------------------------------
# 5. Validate signup date vs order date
# ---------------------------------------------------

customers["SignupDate"] = pd.to_datetime(
    customers["SignupDate"], errors="coerce"
)

joined = orders.merge(
    customers,
    on="CustomerID",
    how="left",
    validate="many_to_one"
)

invalid_signup_orders = joined.loc[
    joined["SignupDate"].notna()
    & joined["OrderDate"].notna()
    & (
        joined["OrderDate"]
        < joined["SignupDate"].dt.normalize()
    )
].copy()

# ---------------------------------------------------
# 6. Cross-validation
# ---------------------------------------------------

assert (
    int(restaurant_valid.sum()) + len(restaurant_orphans)
    == len(orders)
)

assert (
    int(customer_valid.sum()) + len(customer_orphans)
    == len(orders)
)

assert (
    int(date_valid.sum()) + len(date_orphans)
    == len(orders)
)

# ---------------------------------------------------
# 7. Summary
# ---------------------------------------------------

checks = {
    "Total Orders": len(orders),
    "Valid Restaurant References": int(restaurant_valid.sum()),
    "Invalid Restaurant References": len(restaurant_orphans),
    "Valid Customer References": int(customer_valid.sum()),
    "Invalid Customer References": len(customer_orphans),
    "Valid Date References": int(date_valid.sum()),
    "Invalid Date References": len(date_orphans),
    "Orders Before Customer Signup": len(invalid_signup_orders),
}

summary = pd.DataFrame(
    checks.items(),
    columns=["Metric", "Value"]
)

print("\n", summary.to_string(index=False))

# ---------------------------------------------------
# 8. Save evidence
# ---------------------------------------------------

summary.to_csv(
    OUTPUT / "relationship_summary.csv",
    index=False
)

restaurant_orphans.to_csv(
    OUTPUT / "invalid_restaurant_references.csv",
    index=False
)

customer_orphans.to_csv(
    OUTPUT / "invalid_customer_references.csv",
    index=False
)

date_orphans.to_csv(
    OUTPUT / "invalid_date_references.csv",
    index=False
)

invalid_signup_orders.to_csv(
    OUTPUT / "orders_before_signup.csv",
    index=False
)

print("\n[SUCCESS] 5 validation reports saved.")
print("[SUCCESS] Relationship audit completed.")