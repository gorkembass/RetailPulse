-- Indexes on the fact table's selective filter keys.
-- Each one was kept because it changed the plan and the measured execution time of a
-- selective query; an index on invoice_no was evaluated and rejected. See docs/performance.md
-- and re-measure with sql/performance/explain_analyze.sql before adding or removing any.

CREATE INDEX IF NOT EXISTS idx_fact_sales_date_key
    ON analytics.fact_sales (date_key);

CREATE INDEX IF NOT EXISTS idx_fact_sales_customer_id
    ON analytics.fact_sales (customer_id)
    WHERE customer_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_fact_sales_stock_code
    ON analytics.fact_sales (stock_code);

ANALYZE staging.transactions;
ANALYZE analytics.dim_date;
ANALYZE analytics.dim_product;
ANALYZE analytics.dim_customer;
ANALYZE analytics.fact_sales;
