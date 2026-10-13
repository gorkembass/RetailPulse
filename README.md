# RetailPulse — E-Commerce Analytics

An end-to-end analytics project on a year of real transactions from a UK online retailer: 541,909 invoice lines taken from a raw spreadsheet to a tested PostgreSQL star schema, 31 analytical SQL queries, a pandas metrics layer and an interactive dashboard.

The project answers practical questions. How much did the business sell and keep after returns? Which products, countries and customers does that revenue depend on? Do customers come back? And how much do the answers change with the data-cleaning decisions behind them?

![Sales overview page of the RetailPulse dashboard showing revenue KPIs, monthly gross revenue, monthly return rate, daily revenue trend and international revenue by country](docs/images/dashboard-overview.png)

## Contents

- [Key findings](#key-findings)
- [Architecture](#architecture)
- [Technology stack](#technology-stack)
- [Data source and licence](#data-source-and-licence)
- [Getting started](#getting-started)
- [Running the pipeline](#running-the-pipeline)
- [SQL analyses](#sql-analyses)
- [KPI dictionary](#kpi-dictionary)
- [Data quality](#data-quality)
- [Dashboard](#dashboard)
- [Testing](#testing)
- [Design decisions](#design-decisions)
- [Limitations](#limitations)
- [Repository layout](#repository-layout)

## Key findings

Computed by this pipeline from the UCI Online Retail dataset (1 December 2010 to 9 December 2011, amounts in GBP). The full analysis with supporting tables is in [docs/findings.md](docs/findings.md).

| Metric | Value |
|---|---:|
| Gross revenue | £10,247,219 |
| Net revenue after returns | £9,771,318 |
| Orders | 19,773 |
| Average order value (median) | £518 (£302) |
| Identified customers | 4,334 |
| Return rate | 4.6% |

1. **Revenue peaks before Christmas.** September to November produced 35% of the year's revenue; November was 2.9 times February.
2. **The return rate overstates the returns problem.** Two wholesale orders that were cancelled within minutes account for 52% of all returned value. Without the largest credit note in each month, the monthly rate stays between 0.9% and 2.9%.
3. **Sales are concentrated.** The top 10% of products generate 61% of revenue, and 816 products (21.5% of the range) generate 80%.
4. **Customer value is concentrated too.** The Champions segment is 23% of customers and 66.5% of net revenue. 214 At Risk customers hold £378k of historical revenue and have not ordered for four months on average.
5. **Overseas revenue is account risk.** The Netherlands and EIRE are the second and third largest markets with nine and three customers respectively.
6. **Retention is steady at about one in four.** 22.5% of customers order again in the month after their first purchase, rising to 27% by month six.
7. **Cleaning choices matter less than definitions.** Keeping duplicate lines would change revenue by 0.24%; dropping rows without a customer ID, a common shortcut, would remove 14.7%.

Profit is not reported because the dataset has no cost data. See [Revenue versus profitability](docs/kpi_dictionary.md#revenue-versus-profitability).

## Architecture

![Architecture diagram: the UCI source file flows into an immutable raw layer, through pandas cleaning rules into a processed layer, into PostgreSQL staging and analytics schemas, and out to SQL analyses, pandas analytics, a Streamlit dashboard and Power BI exports, with Pytest verifying that SQL and pandas agree](docs/images/architecture.svg)

| Layer | Location | Purpose |
|---|---|---|
| Raw | `data/raw/` | Source file as downloaded, with a SHA-256 checksum. Never modified. |
| Processed | `data/processed/` | Every source row, typed and classified as `sale`, `return` or `excluded` with a reason. |
| Staging | PostgreSQL `staging` | Typed copy of the processed layer, including excluded rows, for auditing in SQL. |
| Analytics | PostgreSQL `analytics` | Star schema: `fact_sales`, `dim_date`, `dim_product`, `dim_customer`, plus order and RFM views. |
| Outputs | `data/processed/`, `dashboard/exports/` | SQL results, pandas analytics tables and star schema CSVs. |

The schema diagram and module responsibilities are in [docs/architecture.md](docs/architecture.md).

## Technology stack

| Area | Tools |
|---|---|
| Language | Python 3.11+ |
| Data processing | pandas 3, PyArrow, openpyxl |
| Database | PostgreSQL 16, SQLAlchemy 2, psycopg 3 |
| Dashboard | Streamlit, Plotly; star schema exports for Power BI |
| Testing and quality | Pytest, Ruff |
| Infrastructure | Docker, Docker Compose |

## Data source and licence

| | |
|---|---|
| Dataset | Online Retail, UCI Machine Learning Repository |
| URL | https://archive.ics.uci.edu/dataset/352/online+retail |
| Licence | [Creative Commons Attribution 4.0 International (CC BY 4.0)](https://creativecommons.org/licenses/by/4.0/) |
| Citation | Chen, D. (2015). Online Retail [Dataset]. UCI Machine Learning Repository. https://doi.org/10.24432/C5BW33 |
| Size | 541,909 rows, one 23.7 MB Excel workbook |
| Period | 1 December 2010 to 9 December 2011 |

| Column | Type | Description |
|---|---|---|
| `InvoiceNo` | Text | Six-digit invoice number. A `C` prefix marks a cancellation. |
| `StockCode` | Text | Product code, normally five digits with an optional letter suffix. |
| `Description` | Text | Product name. |
| `Quantity` | Integer | Units on the line. Negative on cancellations and stock adjustments. |
| `InvoiceDate` | Timestamp | Date and time the invoice was generated. |
| `UnitPrice` | Decimal | Price per unit in pounds sterling. |
| `CustomerID` | Integer | Five-digit customer number. Missing on 24.9% of rows. |
| `Country` | Text | Country where the customer resides. |

The dataset is not stored in this repository. `retailpulse ingest` downloads it from UCI and records the URL, licence, retrieval time and checksum in `data/raw/source_metadata.json`.

**Synthetic fallback.** If the download fails, or with `--source synthetic`, the pipeline uses a small seeded dataset in the same layout. It exists for CI and offline development. It is recorded as synthetic in the metadata and flagged with a banner in the dashboard. Every figure in this README comes from the real UCI data.

## Getting started

Requirements: Python 3.11 or newer, Docker with Docker Compose, and `make` (optional; each target is a one-line command).

```bash
make install        # virtual environment + dependencies
cp .env.example .env
make db-up          # PostgreSQL 16 on localhost:5432
make pipeline       # download, clean, load, analyse, export (about one minute)
make test           # unit and PostgreSQL integration tests
make dashboard      # http://localhost:8501
```

Without `make`:

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dashboard,dev]"
docker compose up -d --wait postgres
.venv/bin/retailpulse run
RETAILPULSE_TEST_DATABASE_URL=postgresql+psycopg://retailpulse:retailpulse@localhost:5432/retailpulse_test .venv/bin/pytest
.venv/bin/streamlit run dashboard/app.py
```

### Fully containerised

Nothing but Docker is needed on the host:

```bash
docker compose up -d --wait postgres
docker compose run --rm app                    # full pipeline on the UCI data
docker compose run --rm app pytest             # tests inside the container
docker compose --profile dashboard up dashboard
```

Connection settings are read from the environment; `.env.example` lists them. The values there are local development defaults, not secrets.

## Running the pipeline

`retailpulse run` executes every step. Each can also be run on its own:

| Step | Command | Output |
|---|---|---|
| 1. Acquire data | `retailpulse ingest [--source auto\|uci\|synthetic] [--force]` | `data/raw/online_retail.xlsx`, `source_metadata.json` |
| 2. Clean and classify | `retailpulse clean` | `data/processed/transactions.parquet`, `products.parquet`, `quality/*.csv` |
| 3. Load the warehouse | `retailpulse load` | `staging` and `analytics` schemas |
| 4. Run SQL analyses | `retailpulse sql` | `data/processed/sql_results/*.csv`, one file per query |
| 5. Run pandas analytics | `retailpulse analyze` | `data/processed/analytics/*.csv` |
| 6. Export for Power BI | `retailpulse export` | `dashboard/exports/*.csv` |

Raw data is immutable: `ingest` stops if the file already exists unless `--force` is given.

## SQL analyses

Thirty-one named queries in six files under [`sql/analysis/`](sql/analysis). Each query is delimited by a `-- name:` comment and is exported to its own CSV.

| File | Contents | Techniques |
|---|---|---|
| [`01_sales_overview.sql`](sql/analysis/01_sales_overview.sql) | Headline KPIs, revenue by country, domestic versus international, order-value bands, margin scenarios | CTEs, `FILTER`, `PERCENTILE_CONT`, `CASE`, window shares |
| [`02_product_performance.sql`](sql/analysis/02_product_performance.sql) | Product ranking with Pareto share, revenue deciles, category performance, monthly category leaders, most-returned products | Running totals, `NTILE`, `DENSE_RANK`, outer joins |
| [`03_customer_segmentation.sql`](sql/analysis/03_customer_segmentation.sql) | RFM scores and segments, new versus returning customers, repeat purchase rate, customer value deciles | `RANK`, tie-safe scoring, `CASE` segment grid |
| [`04_cohort_retention.sql`](sql/analysis/04_cohort_retention.sql) | Cohort retention, pivoted retention matrix, weighted average retention | Date arithmetic, `GENERATE_SERIES`, `LATERAL`, conditional pivot |
| [`05_revenue_trends.sql`](sql/analysis/05_revenue_trends.sql) | Monthly and daily trends, weekday and hour pattern, best and worst days, returns impact | `LAG`, moving average frames, calendar join for gap filling |
| [`06_data_quality.sql`](sql/analysis/06_data_quality.sql) | Exclusions by rule, duplicate re-check, missing customers by month, rule sensitivity, warehouse reconciliation | `ROW_NUMBER` de-duplication, scalar subqueries, anti-join |

### Example: tie-safe RFM scoring

`NTILE(5)` would split customers with identical values across buckets, and a third of customers are tied on one order. This view scores each customer by the share of customers ranked strictly below them, so equal values always receive the same score. From [`sql/schema/02_analytics.sql`](sql/schema/02_analytics.sql):

```sql
ranked AS (
    SELECT
        m.customer_id,
        s.snapshot_date - m.last_order_date                             AS recency_days,
        m.frequency,
        m.monetary,
        COUNT(*) OVER ()                                                AS customer_count,
        RANK() OVER (ORDER BY s.snapshot_date - m.last_order_date DESC) AS recency_rank,
        RANK() OVER (ORDER BY m.frequency)                              AS frequency_rank,
        RANK() OVER (ORDER BY m.monetary)                               AS monetary_rank
    FROM customer_metrics AS m
    CROSS JOIN snapshot AS s
),
scored AS (
    SELECT
        customer_id,
        (5 * (recency_rank - 1) / customer_count + 1)::int              AS r_score,
        (5 * (frequency_rank - 1) / customer_count + 1)::int            AS f_score,
        (5 * (monetary_rank - 1) / customer_count + 1)::int             AS m_score
    FROM ranked
)
```

### Example: separating systemic returns from one-off reversals

From [`05_revenue_trends.sql`](sql/analysis/05_revenue_trends.sql):

```sql
WITH credit_notes AS (
    SELECT
        d.month_start,
        f.invoice_no,
        -SUM(f.line_amount) AS credit_value
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    WHERE f.line_type = 'return'
    GROUP BY d.month_start, f.invoice_no
),
monthly_returns AS (
    SELECT
        month_start,
        COUNT(*)            AS credit_notes,
        SUM(credit_value)   AS return_value,
        MAX(credit_value)   AS largest_credit_note
    FROM credit_notes
    GROUP BY month_start
)
```

| period | gross_revenue | return_value | return_rate | largest_credit_note | return_rate_excl_largest |
|---|---:|---:|---:|---:|---:|
| 2011-01-01 | 670,380.24 | 91,525.05 | 0.1365 | 77,183.60 | 0.0214 |
| 2011-11-01 | 1,452,115.98 | 24,991.44 | 0.0172 | 2,506.00 | 0.0155 |
| 2011-12-01 | 614,490.92 | 174,091.36 | 0.2833 | 168,469.60 | 0.0091 |

### Indexes and query plans

Indexes on `fact_sales` were chosen by measurement. [`sql/performance/explain_analyze.sql`](sql/performance/explain_analyze.sql) runs each probe with and without its index inside a rolled-back transaction (`make explain`). Three indexes cut selective lookups from about 8,000 pages to under 300; a fourth, on `invoice_no`, produced an identical plan with and without it and was removed. Method, plans and timings are in [docs/performance.md](docs/performance.md).

## KPI dictionary

Each KPI is documented with its business definition, calculation, SQL and Python implementation, and the decisions it supports in [docs/kpi_dictionary.md](docs/kpi_dictionary.md).

| KPI | Definition | SQL | Python |
|---|---|---|---|
| Gross revenue | `SUM(quantity * unit_price)` over valid sale lines | `01` → `headline_kpis` | `sales.kpi_summary` |
| Return value, return rate | Credit-note value; as a share of gross revenue | `05` → `returns_impact_by_month` | `sales.revenue_trend` |
| Net revenue | Gross revenue minus return value | `01` → `headline_kpis` | `sales.kpi_summary` |
| Orders | Distinct invoices with at least one sale line | `analytics.v_orders` | `base.orders` |
| Average and median order value | Gross revenue per order; 50th percentile | `01` → `headline_kpis` | `sales.kpi_summary` |
| Revenue trend | Monthly and daily revenue, growth, 7-day average | `05` → `monthly_revenue_trend` | `sales.revenue_trend` |
| Product and category performance | Revenue, units, returns, Pareto share | `02` → `product_performance` | `products.product_performance` |
| Revenue by country | Revenue, orders, customers and share | `01` → `revenue_by_country` | `sales.country_performance` |
| New versus returning | Revenue by first-time and repeat buyers | `03` → `new_vs_returning_by_month` | `customers.new_vs_returning` |
| RFM segments | Recency, frequency and monetary scores, 9 segments | `analytics.v_customer_rfm` | `customers.rfm_scores` |
| Cohort retention | Share of a monthly cohort active N months later | `04` → `cohort_retention` | `cohorts.cohort_retention` |
| Assumed margin scenarios | Net revenue under assumed COGS ratios; not a measured KPI | `01` → `revenue_vs_assumed_margin` | `profitability.margin_scenarios` |

## Data quality

No row is deleted. Every source row is classified, and excluded rows keep the rule that excluded them. Details, the full rule table and sensitivity analysis are in [docs/data_quality.md](docs/data_quality.md).

| Issue | Handling | Rows |
|---|---|---:|
| Missing customer ID | Kept as revenue and flagged; left out of customer-level analyses only | 135,080 |
| Exact duplicate lines | First occurrence kept, repeats excluded; revenue impact reported (0.24%) | 5,268 |
| Zero or negative price | Excluded as free items and corrections | 1,161 |
| Negative quantity on a credit note | Classified as a return; reduces net revenue | 8,668 |
| Negative quantity without a credit note | Excluded as a stock write-off | 1,336 |
| Non-merchandise codes (postage, fees, manual) | Excluded from merchandise revenue | 2,947 |
| Invalid invoice numbers | Excluded as accounting adjustments | 3 |
| Invalid dates, quantities or prices | Rule implemented and tested; none found in this dataset | 0 |

Result: 522,537 sale lines, 8,668 return lines and 10,704 excluded lines (2.0% of rows).

![Data quality page of the dashboard showing counts of sale, return and excluded lines, the excluded rows by rule, the share of revenue without a customer ID by month, and the duplicate rule sensitivity](docs/images/dashboard-data-quality.png)

## Dashboard

A four-page Streamlit application with date and market filters. It calls the same tested functions as the pipeline, so filtered views are recomputed from line-level data instead of being read from pre-aggregated files.

```bash
make dashboard      # or: docker compose --profile dashboard up dashboard
```

The screenshots in this README were captured from the running application on the UCI data.

**Products**: category mix, revenue concentration and return rates.

![Products page of the dashboard showing revenue by derived category, return rate by category, the top fifteen products by net revenue and the products with the highest return rate](docs/images/dashboard-products.png)

**Customers**: RFM segments, new versus returning revenue and cohort retention.

![Customers page of the dashboard showing RFM segment shares of customers and of net revenue, monthly revenue split by new, returning and unidentified customers, and a monthly cohort retention heatmap](docs/images/dashboard-customers.png)

### Power BI

Power BI Desktop does not run on macOS, where this project was built, so **no Power BI report is included and none has been tested**. `retailpulse export` writes the star schema to `dashboard/exports/` in a form Power BI imports directly. [docs/powerbi_guide.md](docs/powerbi_guide.md) describes the relationships, DAX measures and the expected values to validate them against.

## Testing

```bash
make test           # all tests; integration tests need PostgreSQL running
make test-unit      # tests that need no database
make lint           # ruff check and format check
```

Latest local run (Python 3.14, PostgreSQL 16.15):

```text
tests/test_cleaning_rules.py              25 passed
tests/test_cohorts.py                      8 passed
tests/test_duplicates.py                   7 passed
tests/test_edge_cases.py                  22 passed
tests/test_ingestion.py                   16 passed
tests/test_integration_postgres.py        18 passed
tests/test_returns.py                      7 passed
tests/test_rfm.py                         20 passed
tests/test_sales_metrics.py               12 passed
---------------------------------------------------
135 passed
```

| Area | File | What is verified |
|---|---|---|
| Cleaning rules | `test_cleaning_rules.py` | Each exclusion rule, rule precedence, type normalisation, that no row is dropped |
| Duplicates | `test_duplicates.py` | First occurrence kept, near-duplicates preserved, revenue sensitivity |
| Returns | `test_returns.py` | Credit notes, stock adjustments, fully reversed orders, effect on net revenue |
| Revenue | `test_sales_metrics.py` | KPIs, trends, country, product and category tables, reconciliation of returns |
| RFM | `test_rfm.py` | Metrics, tie-safe scoring, the segment grid, monetary net of returns |
| Cohorts | `test_cohorts.py` | Cohort sizes, retention rates, zero-activity months, year boundaries |
| Edge cases | `test_edge_cases.py` | Empty input, missing columns, data without customers, unsupported files |
| Ingestion | `test_ingestion.py` | Deterministic synthetic data, raw immutability, labelled fallback, SQL file parsing |
| PostgreSQL | `test_integration_postgres.py` | Loading, constraints, reconciliation, and that each SQL analysis equals its pandas counterpart |

The integration tests load the synthetic dataset into a separate `retailpulse_test` database and are skipped when `RETAILPULSE_TEST_DATABASE_URL` is not set.

## Design decisions

- **Classify, do not delete.** Exclusions are labels, so their effect on every metric can be measured and reported.
- **Two implementations, tested against each other.** SQL and pandas compute the same metrics independently. On the real data this comparison exposed products with returns but no sales being dropped from product totals; the fix and a regression test are in the repository.
- **Net revenue for rankings.** Gross revenue ranks a fully cancelled order as the second-best product.
- **Tie-safe RFM scores** in place of `NTILE`, so equal customers are never scored differently.
- **Unobserved is not zero.** Cohort periods after the end of the data are empty; periods a cohort reached without purchases are zero.
- **Measured indexes only.** One index was removed after `EXPLAIN ANALYZE` showed it changed nothing.
- **Full refresh.** The source is a fixed extract; rebuilding takes seconds and avoids incremental-state bugs.
- **No profit figure.** Without cost data, only labelled scenarios are shown.

More detail is in [docs/architecture.md](docs/architecture.md#design-decisions).

## Limitations

- **One year of data**, with a partial final month. Seasonality is seen once and cannot be separated from growth.
- **Left truncation.** Customers who first bought before December 2010 appear as new.
- **14.7% of revenue has no customer ID** and is missing from customer-level results.
- **Returns cannot be linked to their original sales**, so return rates compare credit notes and sales of the same period.
- **Product categories are derived** from description keywords and are approximate; 4.5% of revenue is uncategorised.
- **No cost, marketing or traffic data**, so profitability, acquisition cost and conversion are out of scope.
- **Power BI report not built**; exports and a build guide are provided instead.
- **Performance measurements** come from one laptop and one data size.
- **Batch only.** The pipeline is a full refresh and has no scheduling or incremental loading.

## Repository layout

```text
├── dashboard/                    Streamlit app; exports/ receives Power BI CSVs
├── data/
│   ├── raw/                      Immutable source data (not committed)
│   └── processed/                Cleaned data and analysis outputs (not committed)
├── docker/initdb/                Creates the integration-test database
├── docs/                         Architecture, KPI dictionary, data quality, findings, performance
├── sql/
│   ├── schema/                   Staging tables, star schema, indexes
│   ├── analysis/                 01–06 analytical queries
│   └── performance/              EXPLAIN ANALYZE probes
├── src/retailpulse/
│   ├── ingestion/                Download, raw reader, synthetic generator
│   ├── cleaning/                 Classification rules, products, quality reports
│   ├── analytics/                Metric and analysis logic
│   ├── database/                 Connection, loading, SQL runner, export
│   ├── pipeline.py               Step orchestration
│   └── cli.py                    retailpulse command
├── tests/                        Unit and integration tests
├── docker-compose.yml
├── Dockerfile
├── Makefile
└── pyproject.toml
```

## Licence

Code is released under the [MIT Licence](LICENSE). The UCI Online Retail dataset is licensed separately by its authors under CC BY 4.0 and is not redistributed here.
