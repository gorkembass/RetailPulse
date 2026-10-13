# KPI dictionary

All amounts are in pounds sterling. Unless stated otherwise, a metric is computed over **valid lines**: rows classified as `sale` or `return` by the rules in [data_quality.md](data_quality.md).

- A **sale line** has a six-digit invoice number, a merchandise stock code, a positive quantity and a positive price.
- A **return line** belongs to a credit note (invoice number prefixed with `C`) and has a negative quantity.
- An **order** is an invoice with at least one sale line. Credit notes are separate invoices and are not orders.

Python implementations are in `src/retailpulse/analytics/`. SQL implementations are named queries in `sql/analysis/`.

## Revenue and orders

### Gross revenue
| | |
|---|---|
| Business definition | Value of merchandise invoiced to customers, before returns. Postage, fees and manual adjustments are not merchandise and are excluded. |
| Calculation | `SUM(quantity * unit_price)` over sale lines |
| SQL | `01_sales_overview.sql` → `headline_kpis` |
| Python | `sales.kpi_summary` → `gross_revenue` |
| Use | Measures demand and sales activity. Use it for trend, seasonality and mix. Do not use it to judge what the business kept. |

### Return value and return rate
| | |
|---|---|
| Business definition | Value of merchandise credited back to customers, and that value as a share of gross revenue. |
| Calculation | `return_value = -SUM(line_amount)` over return lines; `return_rate = return_value / gross_revenue` |
| SQL | `headline_kpis`; by month in `05_revenue_trends.sql` → `returns_impact_by_month`; by product in `02_product_performance.sql` → `most_returned_products` |
| Python | `sales.kpi_summary`, `sales.revenue_trend`, `products.product_performance` |
| Use | Flags product quality, description or fulfilment problems. Always read it next to `return_rate_excl_largest`, because single cancelled wholesale orders dominate some months. |
| Caveat | A return is dated by its credit note and cannot be linked to the original invoice, so a monthly rate compares returns issued in a month with sales made in that month. |

### Net revenue
| | |
|---|---|
| Business definition | Merchandise revenue the business retained after returns. |
| Calculation | `gross_revenue - return_value`, equal to `SUM(line_amount)` over all valid lines |
| SQL | `headline_kpis`, `monthly_revenue_trend` |
| Python | `sales.kpi_summary` → `net_revenue` |
| Use | The revenue figure to report and to rank products on. Ranking on gross revenue puts a fully cancelled £168k order at number two. |

### Orders
| | |
|---|---|
| Business definition | Number of customer orders placed. |
| Calculation | `COUNT(DISTINCT invoice_no)` over sale lines |
| SQL | `headline_kpis`; order grain in the `analytics.v_orders` view |
| Python | `base.orders`, `sales.kpi_summary` → `orders` |
| Use | Volume driver of revenue. Splitting revenue change into orders and order value shows whether growth came from more buying or bigger baskets. |

### Average and median order value
| | |
|---|---|
| Business definition | Typical value of one order. |
| Calculation | `AOV = gross_revenue / orders`; median is the 50th percentile of order values (`PERCENTILE_CONT(0.5)`) |
| SQL | `headline_kpis`; distribution in `order_value_distribution` |
| Python | `sales.kpi_summary` → `average_order_value`, `median_order_value` |
| Use | Sets free-shipping thresholds and minimum order values. The mean (£518) is 71% above the median (£302) because of a few very large wholesale orders, so the median describes a typical order better. |

### Units sold
| | |
|---|---|
| Business definition | Number of items invoiced. |
| Calculation | `SUM(quantity)` over sale lines |
| SQL / Python | `headline_kpis` / `sales.kpi_summary` → `units_sold` |
| Use | Inventory and fulfilment planning; separates price effects from volume effects. |

## Trends

### Monthly and daily revenue
| | |
|---|---|
| Business definition | Revenue over time, with month-over-month growth and a seven-day average that smooths weekday effects. |
| Calculation | Aggregation by `dim_date.month_start` or `date_key`; growth uses `LAG`; the daily series joins from `dim_date` so non-trading days are zero and the window always spans seven calendar days |
| SQL | `05_revenue_trends.sql` → `monthly_revenue_trend`, `daily_revenue_trend`, `weekday_hour_pattern`, `best_and_worst_days` |
| Python | `sales.revenue_trend(freq="M" or "D")`, `sales.weekday_hour_pattern` |
| Use | Seasonality planning for stock and staffing. `gross_revenue_per_trading_day` corrects for months with different numbers of trading days and for the partial final month. |

## Products and geography

### Product performance and revenue concentration
| | |
|---|---|
| Business definition | Revenue, units and returns per product, with each product's cumulative share of revenue. |
| Calculation | Aggregation by `stock_code`; rank by gross revenue; `cumulative_revenue_share` is a running `SUM` over that order divided by the total |
| SQL | `02_product_performance.sql` → `product_performance`, `revenue_concentration` |
| Python | `products.product_performance` |
| Use | Range decisions: which products deserve guaranteed availability and which long-tail lines to review. |

### Category performance
| | |
|---|---|
| Business definition | Revenue and return rate by product category. |
| Calculation | Aggregation by `dim_product.category` |
| SQL | `02_product_performance.sql` → `category_performance`, `category_monthly_leaders` |
| Python | `products.category_performance` |
| Use | Merchandising focus and seasonal planning. |
| Caveat | The source has no category field. Categories are assigned by keyword rules on product descriptions (`cleaning/products.py`); 4.5% of revenue falls into `Other`. They are an approximation, not a merchandising hierarchy. |

### Revenue by country
| | |
|---|---|
| Business definition | Revenue, orders and customers by the country on the invoice. |
| Calculation | Aggregation by `fact_sales.country` with share of total and rank |
| SQL | `01_sales_overview.sql` → `revenue_by_country`, `domestic_vs_international` |
| Python | `sales.country_performance` |
| Use | Market prioritisation. Customer counts matter as much as revenue here: several high-revenue countries depend on fewer than ten customers. |

## Customers

Customer metrics cover only orders with a customer ID: 93.1% of orders and 85.3% of gross revenue.

### New and returning customers
| | |
|---|---|
| Business definition | Monthly revenue split by whether the buyer is ordering for the first time. |
| Calculation | An order is `new` when its month equals the customer's first-order month, `returning` otherwise, `unidentified` when it has no customer ID |
| SQL | `03_customer_segmentation.sql` → `new_vs_returning_by_month`, `repeat_purchase_rate` |
| Python | `customers.new_vs_returning`, `customers.repeat_purchase_rate` |
| Use | Balances acquisition spend against retention spend. |
| Caveat | The data starts on 1 December 2010. Customers who bought earlier are counted as new when they first appear, which overstates new customers in the first months. |

### RFM segmentation
| | |
|---|---|
| Business definition | Customer segments built from how recently, how often and how much each customer bought. |
| Calculation | Recency: days from last order to the day after the last sale in the data. Frequency: number of orders. Monetary: net revenue. Each is scored 1 to 5 as `5 * (RANK() - 1) / COUNT(*) + 1` using integer division, so tied customers share a score. Segments come from a 3×3 grid of recency and frequency scores. |
| SQL | `analytics.v_customer_rfm` view; `03_customer_segmentation.sql` → `rfm_scores`, `rfm_segment_summary` |
| Python | `customers.rfm_scores`, `customers.assign_segment`, `customers.rfm_segment_summary` |
| Use | Targeting: retention offers for At Risk, a second-order incentive for New Customers, no discounting for Champions. |

Segment grid:

| | Frequency score 4–5 | Frequency score 2–3 | Frequency score 1 |
|---|---|---|---|
| **Recency score 4–5** | Champions | Potential Loyalists | New Customers |
| **Recency score 3** | Loyal Customers | Needs Attention | Promising |
| **Recency score 1–2** | At Risk | Hibernating | Lost |

### Cohort retention
| | |
|---|---|
| Business definition | Share of the customers acquired in a month who order again N months later. |
| Calculation | Cohort is the month of the first order. `retention_rate = active customers in month N / cohort size`. Months a cohort has reached with no purchases count as zero; months after the end of the data are left empty. |
| SQL | `04_cohort_retention.sql` → `cohort_retention`, `cohort_retention_matrix`, `average_retention_by_period` |
| Python | `cohorts.cohort_retention`, `cohorts.retention_matrix`, `cohorts.average_retention` |
| Use | Shows whether newer cohorts retain better or worse than older ones, which is the earliest signal of a change in customer quality. |

## Revenue versus profitability

The dataset contains no cost of goods, shipping cost, fees or discounts, so **profit cannot be measured and no profit KPI is reported**.

What the project does report:

1. **The gap between gross and net revenue**, which is measured: £475,901 of returns, 4.6% of gross revenue.
2. **A labelled scenario table** (`revenue_vs_assumed_margin` in SQL, `profitability.margin_scenarios` in Python) that applies assumed cost-of-goods ratios of 50%, 60% and 70% to net revenue. Its columns are prefixed `assumed_`. It exists to show how sensitive margin is to cost assumptions, and it must not be quoted as the company's margin.

Even with cost data, the excluded non-product lines would matter for profitability: they include £221,520 of marketplace fees and £272,476 of postage charged to customers (codes `POST` and `DOT`).
