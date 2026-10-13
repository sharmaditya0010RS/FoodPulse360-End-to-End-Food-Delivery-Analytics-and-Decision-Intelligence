# FoodPulse360

### End-to-End Food Delivery Analytics & Decision Intelligence

FoodPulse 360 is an end-to-end data analytics project that transforms simulated food-delivery transactions into a validated PostgreSQL analytics warehouse and an interactive Streamlit dashboard.

The project combines data engineering, SQL, statistical validation, customer segmentation, retention analysis, restaurant performance monitoring, and scenario-based decision support.

## Project at a Glance

| Metric | Value |
|---|---:|
| Orders analyzed | 200,000 |
| Customers | 20,000 |
| Restaurants in source data | 56,250 |
| Restaurants with observed orders | 54,600 |
| Observation period | January 2023 – September 26, 2025 |
| Recorded order value | ₹164.91 million |
| Confirmed delivered order value | ₹132.09 million |
| Recovery candidates identified | 2,431 |
| Interactive dashboard pages | 9 |
| Automated QA assertions passed | 58/58 |

**Important:** Recorded order value is the face value of customer orders, not platform revenue or profit. The dataset is simulated, and findings should not be interpreted as real-world operational outcomes.

## Business Questions

FoodPulse 360 explores the following questions:

1. How do order volumes and recorded order values change over time?
2. How frequently are orders delivered, delayed, or cancelled?
3. Which restaurants contribute the most order value?
4. Which restaurants may warrant operational review?
5. How can customers be segmented by recency, frequency, and monetary value?
6. What does observed customer retention look like?
7. Which historically valuable customers have become inactive?
8. Under what assumptions might a customer recovery campaign become financially viable?
9. How reliable are the underlying data and business metrics?

## Technology Stack

- **Python:** Data cleaning, ETL, validation, and analytics
- **Pandas:** Data transformation and aggregation
- **PostgreSQL:** Analytics warehouse, fact tables, dimensions, and reporting views
- **SQLAlchemy and psycopg:** Database connectivity
- **Streamlit:** Interactive analytics dashboard
- **Plotly:** Interactive charts and visualizations
- **Git and GitHub:** Version control and portfolio presentation

## Data Architecture

The solution follows a layered analytical workflow:

**Source Excel Dataset → Data Cleaning → Validated Analytics Mart → PostgreSQL Warehouse → SQL Reporting Views → Streamlit Dashboard**

The warehouse includes order facts, customer and restaurant dimensions, a date dimension, and reporting views supporting executive, monthly, delivery, customer, and restaurant analysis.

## Interactive Dashboard

The dashboard includes nine pages:

1. **Executive Command Center** — Business KPIs and overall performance
2. **Revenue & Growth** — Monthly trends, order values, and growth comparisons
3. **Delivery & Cancellation** — Delivery outcomes and cancellation patterns
4. **Restaurant Performance** — Restaurant rankings and operational indicators
5. **Customer Intelligence** — Stable RFM customer segmentation
6. **Retention & Reactivation** — Customer activity and observed retention
7. **Recovery Opportunities** — Inactive high-value customer identification
8. **Scenario Simulator** — Hypothetical campaign economics and break-even analysis
9. **Data Trust Center** — Data-quality issues, limitations, and metric definitions

## Selected Analytical Findings

### Customer Segmentation

The project uses stable, tie-consistent RFM scoring to classify 20,000 customers into behavioral segments.

The Champions segment contains 3,416 customers and accounts for approximately 23.74% of recorded order value.

### Retention and Customer Activity

A total of 19,989 customers placed at least two observed orders. This high observed repeat-customer rate is not equivalent to next-calendar-month cohort retention, which is substantially lower.

Based on activity relative to the dataset's final observation date, 8,053 customers had not placed an observed order for more than 90 days.

### Recovery Opportunities

The analysis identifies 2,431 historically high-value customers who were inactive for more than 90 days.

- **Tier 1:** 1,939 customers with high historical frequency and value
- **Tier 2:** 492 additional high-value customers

Their historical confirmed delivered order value totals ₹21,076,712.

This figure represents past activity, not expected future revenue or recoverable financial value.

### Campaign Scenario Analysis

The scenario simulator allows users to adjust targeting, incremental conversion assumptions, contribution margin, average order value, and campaign cost.

It calculates illustrative incremental contribution, campaign cost, and estimated net contribution.

**These scenarios are hypothetical calculations, not causal estimates or financial forecasts.**

## Data Quality and Methodological Limitations

The project explicitly documents important limitations:

- The dataset is simulated.
- Recorded order value is not platform revenue.
- Cancelled order face value is not necessarily a financial loss.
- The final observed month, September 2025, is incomplete.
- Some orders appear before the customer's recorded signup date.
- Some restaurant text fields contain suspected quality issues.
- Delivery-time fields have ambiguous meaning for certain order statuses.
- First observed order does not necessarily represent true customer acquisition.
- Historical inactivity does not establish that a marketing campaign can reactivate customers.
- Restaurant risk signals are exploratory and should not be presented as statistically confirmed failures.

These caveats are included to prevent misleading business conclusions.

## Local Setup

### 1. Clone the repository

```bash
git clone YOUR_REPOSITORY_URL
cd foodpulse-360
```

### 2. Create a Python environment

```bash
python -m venv .venv
```

On Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

### 3. Install dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Configure PostgreSQL

Create a `.env` file using `.env.example` as a reference.

```dotenv
PGHOST=localhost
PGPORT=5432
PGDATABASE=foodpulse360
PGUSER=your_postgres_username
PGPASSWORD=your_postgres_password
```

### 5. Prepare the analytics database

The dashboard requires the FoodPulse PostgreSQL warehouse and its reporting views.

The source dataset and generated reports are not included in the public repository by default. They must be supplied and generated locally before the dashboard can run.

Use the scripts in `src/etl/`, `src/warehouse/`, `src/analytics/`, and `src/validation/` according to the project's data preparation workflow.

### 6. Launch the dashboard

```bash
streamlit run dashboard/app.py
```

## Quality Assurance

The project includes automated checks for:

- Dashboard file integrity and Python syntax
- PostgreSQL connectivity
- Required warehouse tables and views
- Executive KPI reconciliation
- Monthly and order-status totals
- Customer activity and RFM consistency
- Recovery candidate counts and priority tiers

The latest local verification completed with **58 passing assertions and zero failures**.

The nine dashboard pages and their interactive controls were also manually tested.

## Future Improvements

- Add a reproducible, one-command database setup
- Provide a safe sample dataset for demonstration
- Add automated UI regression tests
- Extend financial analysis using actual commissions and operating costs
- Add campaign experimentation to estimate incremental effects
- Prepare a deployment environment with managed PostgreSQL

## Project Purpose

FoodPulse 360 demonstrates how to build an analytics solution that combines engineering, business interpretation, data validation, and interactive decision support.

The emphasis is not only on generating charts, but also on ensuring that reported metrics are reproducible, correctly defined, and presented with appropriate limitations.
