# Building the dashboard in Power BI

Power BI Desktop runs only on Windows, and this project was developed on macOS. **No Power BI report has been built or tested for this repository, and there are no Power BI screenshots.** What the project provides is a star schema that Power BI can import directly, and this guide for building the report. The Streamlit dashboard in `dashboard/` is the implemented and tested alternative.

## Data

`retailpulse export` (also the last step of `retailpulse run`) writes these files to `dashboard/exports/`:

| File | Grain | Rows (UCI data) |
|---|---|---:|
| `fact_sales.csv` | One valid sale or return line | 531,205 |
| `dim_date.csv` | One calendar day | 374 |
| `dim_product.csv` | One stock code | 3,812 |
| `dim_customer.csv` | One identified customer | 4,362 |
| `customer_rfm.csv` | One customer with at least one sale, with RFM scores and segment | 4,334 |

Alternatively, connect Power BI to PostgreSQL (`localhost:5432`, database `retailpulse`) and import the same tables from the `analytics` schema.

## Model

Import the five files, then set these in Model view:

| From (many) | To (one) | Cardinality | Filter direction |
|---|---|---|---|
| `fact_sales[date_key]` | `dim_date[date_key]` | Many to one | Single |
| `fact_sales[stock_code]` | `dim_product[stock_code]` | Many to one | Single |
| `fact_sales[customer_id]` | `dim_customer[customer_id]` | Many to one | Single |
| `customer_rfm[customer_id]` | `dim_customer[customer_id]` | One to one | Both |

Further settings:

- Set `stock_code` and `invoice_no` to type Text in Power Query; several stock codes have letter suffixes and would otherwise be read inconsistently.
- Mark `dim_date` as the date table on `date_key`.
- Sort `dim_date[month_name]` by `dim_date[month]`.
- `fact_sales[customer_id]` is blank for about a quarter of lines. Keep those rows; they are revenue.

## Measures

`line_amount` is positive for sales and negative for returns. These measures reproduce the definitions in [kpi_dictionary.md](kpi_dictionary.md):

```DAX
Gross Revenue = CALCULATE ( SUM ( fact_sales[line_amount] ), fact_sales[line_type] = "sale" )

Return Value = - CALCULATE ( SUM ( fact_sales[line_amount] ), fact_sales[line_type] = "return" )

Net Revenue = SUM ( fact_sales[line_amount] )

Orders = CALCULATE ( DISTINCTCOUNT ( fact_sales[invoice_no] ), fact_sales[line_type] = "sale" )

Average Order Value = DIVIDE ( [Gross Revenue], [Orders] )

Return Rate = DIVIDE ( [Return Value], [Gross Revenue] )

Customers =
CALCULATE (
    DISTINCTCOUNT ( fact_sales[customer_id] ),
    fact_sales[line_type] = "sale",
    NOT ISBLANK ( fact_sales[customer_id] )
)

Identified Revenue Share =
DIVIDE (
    CALCULATE ( [Gross Revenue], NOT ISBLANK ( fact_sales[customer_id] ) ),
    [Gross Revenue]
)

Gross Revenue MoM % =
VAR Previous = CALCULATE ( [Gross Revenue], DATEADD ( dim_date[date_key], -1, MONTH ) )
RETURN DIVIDE ( [Gross Revenue] - Previous, Previous )
```

## Validation

Before designing any page, put the measures on a card with no filters and compare them with `data/processed/sql_results/01_sales_overview__headline_kpis.csv`. On the UCI dataset the expected values are:

| Measure | Expected |
|---|---:|
| Gross Revenue | 10,247,219.32 |
| Return Value | 475,901.16 |
| Net Revenue | 9,771,318.16 |
| Orders | 19,773 |
| Customers | 4,334 |
| Average Order Value | 518.24 |

If they differ, check the column types set in Power Query first.

## Suggested pages

These mirror the Streamlit dashboard, so its screenshots in the README can serve as a layout reference.

1. **Sales overview**: KPI cards; gross revenue by `dim_date[month_start]`; return rate by month; top countries excluding the United Kingdom.
2. **Products**: gross revenue by `dim_product[category]`; top products by net revenue; a table of products by return rate with a minimum-revenue filter.
3. **Customers**: customers and `monetary` by `customer_rfm[segment]`; a matrix of `dim_customer[cohort_month]` against months since first order for retention.
4. **Slicers on every page**: `dim_date[date_key]` range and `fact_sales[country]`.

Note that `customer_rfm.csv` holds scores computed over the full period. Unlike the Streamlit dashboard, a Power BI date slicer will not recompute RFM segments.
