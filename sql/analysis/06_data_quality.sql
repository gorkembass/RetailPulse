-- Data-quality audit over staging.transactions, which keeps every source row.
-- These queries verify the cleaning rules independently and quantify what they remove.

-- name: line_type_summary
SELECT
    line_type,
    COUNT(*)                                                AS line_count,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER (), 4)     AS row_share,
    COALESCE(SUM(line_amount), 0)                           AS line_amount
FROM staging.transactions
GROUP BY line_type
ORDER BY line_count DESC;

-- name: exclusion_summary
SELECT
    exclusion_reason,
    COUNT(*)                                                    AS line_count,
    ROUND(COUNT(*)::numeric / (SELECT COUNT(*) FROM staging.transactions), 6) AS row_share,
    COALESCE(SUM(line_amount), 0)                               AS line_amount,
    COUNT(*) FILTER (WHERE NOT has_customer_id)                 AS rows_without_customer,
    MIN(invoice_date)::date                                     AS first_seen,
    MAX(invoice_date)::date                                     AS last_seen
FROM staging.transactions
WHERE line_type = 'excluded'
GROUP BY exclusion_reason
ORDER BY line_count DESC;

-- name: duplicate_recheck
-- Recomputes exact duplicates in SQL and compares them with the flag set by the pipeline.
WITH numbered AS (
    SELECT
        source_row,
        is_duplicate,
        ROW_NUMBER() OVER (
            PARTITION BY invoice_no, stock_code, description, quantity,
                         invoice_date, unit_price, customer_id, country
            ORDER BY source_row
        ) AS occurrence
    FROM staging.transactions
)
SELECT
    COUNT(*) FILTER (WHERE occurrence > 1)                          AS duplicates_found_in_sql,
    COUNT(*) FILTER (WHERE is_duplicate)                            AS duplicates_flagged_by_pipeline,
    COUNT(*) FILTER (WHERE (occurrence > 1) <> is_duplicate)        AS disagreements
FROM numbered;

-- name: missing_customer_by_month
SELECT
    DATE_TRUNC('month', invoice_date)::date                                         AS period,
    COUNT(DISTINCT invoice_no)                                                      AS orders,
    COUNT(DISTINCT invoice_no) FILTER (WHERE NOT has_customer_id)                   AS orders_without_customer,
    SUM(line_amount)                                                                AS gross_revenue,
    COALESCE(SUM(line_amount) FILTER (WHERE NOT has_customer_id), 0)                AS revenue_without_customer,
    ROUND(
        COALESCE(SUM(line_amount) FILTER (WHERE NOT has_customer_id), 0) / SUM(line_amount),
        4
    )                                                                               AS revenue_share_without_customer
FROM staging.transactions
WHERE line_type = 'sale'
GROUP BY 1
ORDER BY 1;

-- name: rule_sensitivity
-- Gross revenue under alternative treatments of the two rules that involve judgement.
SELECT
    SUM(line_amount) FILTER (WHERE line_type = 'sale')                              AS base_gross_revenue,
    SUM(line_amount) FILTER (
        WHERE line_type = 'sale'
           OR (exclusion_reason = 'duplicate_line' AND NOT is_cancellation)
    )                                                                               AS gross_revenue_keeping_duplicates,
    SUM(line_amount) FILTER (
        WHERE line_type = 'sale'
           OR (exclusion_reason = 'non_product_code' AND quantity > 0 AND unit_price > 0)
    )                                                                               AS gross_revenue_including_non_product,
    SUM(line_amount) FILTER (WHERE line_type = 'sale' AND has_customer_id)          AS gross_revenue_identified_only
FROM staging.transactions;

-- name: non_product_codes
SELECT
    stock_code,
    MIN(description)        AS example_description,
    COUNT(*)                AS line_count,
    SUM(line_amount)        AS line_amount
FROM staging.transactions
WHERE exclusion_reason = 'non_product_code'
GROUP BY stock_code
ORDER BY line_count DESC;

-- name: description_consistency
-- Stock codes sold under more than one description; dim_product keeps the most frequent one.
WITH variants AS (
    SELECT
        stock_code,
        COUNT(DISTINCT description) AS description_variants,
        COUNT(*)                    AS line_count
    FROM staging.transactions
    WHERE line_type <> 'excluded'
      AND description IS NOT NULL
    GROUP BY stock_code
)
SELECT
    COUNT(*)                                            AS products,
    COUNT(*) FILTER (WHERE description_variants > 1)    AS products_with_multiple_descriptions,
    MAX(description_variants)                           AS max_variants
FROM variants;

-- name: warehouse_reconciliation
-- Every non-excluded staging row must appear exactly once in the fact table.
SELECT
    (SELECT COUNT(*) FROM staging.transactions)                                 AS staging_rows,
    (SELECT COUNT(*) FROM staging.transactions WHERE line_type <> 'excluded')   AS expected_fact_rows,
    (SELECT COUNT(*) FROM analytics.fact_sales)                                 AS fact_rows,
    (SELECT COALESCE(SUM(line_amount), 0) FROM staging.transactions
      WHERE line_type <> 'excluded')                                            AS expected_net_amount,
    (SELECT COALESCE(SUM(line_amount), 0) FROM analytics.fact_sales)            AS fact_net_amount,
    (SELECT COUNT(*)
       FROM analytics.fact_sales AS f
       LEFT JOIN analytics.dim_product AS p USING (stock_code)
      WHERE p.stock_code IS NULL)                                               AS fact_rows_without_product;
