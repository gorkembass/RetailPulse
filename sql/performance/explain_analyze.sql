-- Index evaluation for analytics.fact_sales.
--
-- Usage:
--   psql "$PSQL_URL" -f sql/performance/explain_analyze.sql
--   docker compose exec -T postgres psql -U retailpulse -d retailpulse < sql/performance/explain_analyze.sql
--
-- Each probe runs twice: once with the index and once without it. The index is dropped
-- (or, for a candidate, created) inside a transaction that is rolled back, so the database
-- is left unchanged. Run the file more
-- than once and compare "Execution Time" across runs; the first run also pays for a cold
-- cache. Interpretation guidance and recorded results are in docs/performance.md.

\timing off
\pset pager off
SET max_parallel_workers_per_gather = 0;

\echo '=== Probe 1: one customer''s order history (idx_fact_sales_customer_id) ==='
\echo '--- with index'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT invoice_no, MIN(invoice_date) AS order_date, SUM(line_amount) AS order_value
FROM analytics.fact_sales
WHERE customer_id = (SELECT customer_id FROM analytics.dim_customer ORDER BY order_count DESC LIMIT 1)
  AND line_type = 'sale'
GROUP BY invoice_no;

BEGIN;
DROP INDEX analytics.idx_fact_sales_customer_id;
\echo '--- without index'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT invoice_no, MIN(invoice_date) AS order_date, SUM(line_amount) AS order_value
FROM analytics.fact_sales
WHERE customer_id = (SELECT customer_id FROM analytics.dim_customer ORDER BY order_count DESC LIMIT 1)
  AND line_type = 'sale'
GROUP BY invoice_no;
ROLLBACK;

\echo '=== Probe 2: one week of sales (idx_fact_sales_date_key) ==='
\echo '--- with index'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT date_key, COUNT(DISTINCT invoice_no) AS orders, SUM(line_amount) AS gross_revenue
FROM analytics.fact_sales
WHERE date_key >= (SELECT MIN(date_key) + 180 FROM analytics.dim_date)
  AND date_key <  (SELECT MIN(date_key) + 187 FROM analytics.dim_date)
  AND line_type = 'sale'
GROUP BY date_key;

BEGIN;
DROP INDEX analytics.idx_fact_sales_date_key;
\echo '--- without index'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT date_key, COUNT(DISTINCT invoice_no) AS orders, SUM(line_amount) AS gross_revenue
FROM analytics.fact_sales
WHERE date_key >= (SELECT MIN(date_key) + 180 FROM analytics.dim_date)
  AND date_key <  (SELECT MIN(date_key) + 187 FROM analytics.dim_date)
  AND line_type = 'sale'
GROUP BY date_key;
ROLLBACK;

\echo '=== Probe 3: one product''s sales (idx_fact_sales_stock_code) ==='
\echo '--- with index'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT line_type, SUM(quantity) AS units, SUM(line_amount) AS amount
FROM analytics.fact_sales
WHERE stock_code = (SELECT MIN(stock_code) FROM analytics.dim_product)
GROUP BY line_type;

BEGIN;
DROP INDEX analytics.idx_fact_sales_stock_code;
\echo '--- without index'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT line_type, SUM(quantity) AS units, SUM(line_amount) AS amount
FROM analytics.fact_sales
WHERE stock_code = (SELECT MIN(stock_code) FROM analytics.dim_product)
GROUP BY line_type;
ROLLBACK;

\echo '=== Probe 4: full-table monthly aggregate (no index expected to help) ==='
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT d.month_start, SUM(f.line_amount) AS gross_revenue
FROM analytics.fact_sales AS f
JOIN analytics.dim_date AS d USING (date_key)
WHERE f.line_type = 'sale'
GROUP BY d.month_start;

\echo '=== Probe 5: order-level view, candidate index on invoice_no (rejected) ==='
\echo '--- current schema (no index on invoice_no)'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT COUNT(*), AVG(order_value) FROM analytics.v_orders;

BEGIN;
CREATE INDEX idx_fact_sales_invoice_no ON analytics.fact_sales (invoice_no);
ANALYZE analytics.fact_sales;
\echo '--- with candidate index'
EXPLAIN (ANALYZE, BUFFERS, COSTS OFF, TIMING OFF, SUMMARY ON)
SELECT COUNT(*), AVG(order_value) FROM analytics.v_orders;
ROLLBACK;

\echo '=== Index sizes ==='
SELECT
    indexrelname                                    AS index_name,
    pg_size_pretty(pg_relation_size(indexrelid))    AS index_size,
    idx_scan                                        AS scans_since_stats_reset
FROM pg_stat_user_indexes
WHERE schemaname = 'analytics' AND relname = 'fact_sales'
ORDER BY indexrelname;

SELECT pg_size_pretty(pg_relation_size('analytics.fact_sales')) AS fact_table_size;
