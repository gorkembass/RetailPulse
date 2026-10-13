-- Cohort retention: customers grouped by first-purchase month and tracked month by month.
-- A cohort has one row for every month it could have been observed in, including months with
-- no purchases (retention 0). Months after the end of the data are unknown and are left out.
-- The final calendar month of the extract is partial, which depresses its retention figures.

-- name: cohort_retention
WITH bounds AS (
    SELECT MAX(d.month_start) AS last_month
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    WHERE f.line_type = 'sale'
),
monthly_activity AS (
    SELECT
        c.cohort_month,
        f.customer_id,
        (
            (d.year - EXTRACT(YEAR FROM c.cohort_month)) * 12
            + d.month - EXTRACT(MONTH FROM c.cohort_month)
        )::int               AS period_index,
        SUM(f.line_amount)   AS gross_revenue
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    JOIN analytics.dim_customer AS c USING (customer_id)
    WHERE f.line_type = 'sale'
    GROUP BY c.cohort_month, f.customer_id, d.year, d.month
),
observed AS (
    SELECT
        cohort_month,
        period_index,
        COUNT(*)            AS active_customers,
        SUM(gross_revenue)  AS gross_revenue
    FROM monthly_activity
    GROUP BY cohort_month, period_index
),
cohort_periods AS (
    SELECT
        o.cohort_month,
        o.active_customers  AS cohort_size,
        p.period_index
    FROM observed AS o
    CROSS JOIN bounds AS b
    CROSS JOIN LATERAL GENERATE_SERIES(
        0,
        (
            (EXTRACT(YEAR FROM b.last_month) - EXTRACT(YEAR FROM o.cohort_month)) * 12
            + EXTRACT(MONTH FROM b.last_month) - EXTRACT(MONTH FROM o.cohort_month)
        )::int
    ) AS p (period_index)
    WHERE o.period_index = 0
)
SELECT
    cp.cohort_month,
    cp.period_index,
    cp.cohort_size,
    COALESCE(o.active_customers, 0)                                     AS active_customers,
    ROUND(COALESCE(o.active_customers, 0)::numeric / cp.cohort_size, 4) AS retention_rate,
    COALESCE(o.gross_revenue, 0)                                        AS gross_revenue
FROM cohort_periods AS cp
LEFT JOIN observed AS o USING (cohort_month, period_index)
ORDER BY cp.cohort_month, cp.period_index;

-- name: cohort_retention_matrix
-- Pivot of selected periods. A period the cohort has not reached yet is NULL, not zero.
WITH bounds AS (
    SELECT MAX(d.month_start) AS last_month
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    WHERE f.line_type = 'sale'
),
activity AS (
    SELECT DISTINCT
        c.cohort_month,
        f.customer_id,
        (
            (d.year - EXTRACT(YEAR FROM c.cohort_month)) * 12
            + d.month - EXTRACT(MONTH FROM c.cohort_month)
        )::int AS period_index
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    JOIN analytics.dim_customer AS c USING (customer_id)
    WHERE f.line_type = 'sale'
),
cohort_counts AS (
    SELECT
        a.cohort_month,
        (
            (EXTRACT(YEAR FROM b.last_month) - EXTRACT(YEAR FROM a.cohort_month)) * 12
            + EXTRACT(MONTH FROM b.last_month) - EXTRACT(MONTH FROM a.cohort_month)
        )::int                                         AS periods_observed,
        COUNT(*) FILTER (WHERE a.period_index = 0)     AS cohort_size,
        COUNT(*) FILTER (WHERE a.period_index = 1)     AS active_1,
        COUNT(*) FILTER (WHERE a.period_index = 2)     AS active_2,
        COUNT(*) FILTER (WHERE a.period_index = 3)     AS active_3,
        COUNT(*) FILTER (WHERE a.period_index = 6)     AS active_6,
        COUNT(*) FILTER (WHERE a.period_index = 9)     AS active_9,
        COUNT(*) FILTER (WHERE a.period_index = 12)    AS active_12
    FROM activity AS a
    CROSS JOIN bounds AS b
    GROUP BY a.cohort_month, b.last_month
)
SELECT
    cohort_month,
    cohort_size,
    CASE WHEN periods_observed >= 1  THEN ROUND(active_1::numeric / cohort_size, 4) END   AS month_1,
    CASE WHEN periods_observed >= 2  THEN ROUND(active_2::numeric / cohort_size, 4) END   AS month_2,
    CASE WHEN periods_observed >= 3  THEN ROUND(active_3::numeric / cohort_size, 4) END   AS month_3,
    CASE WHEN periods_observed >= 6  THEN ROUND(active_6::numeric / cohort_size, 4) END   AS month_6,
    CASE WHEN periods_observed >= 9  THEN ROUND(active_9::numeric / cohort_size, 4) END   AS month_9,
    CASE WHEN periods_observed >= 12 THEN ROUND(active_12::numeric / cohort_size, 4) END  AS month_12
FROM cohort_counts
ORDER BY cohort_month;

-- name: average_retention_by_period
-- Customer-weighted retention across every cohort old enough to have reached the period.
WITH bounds AS (
    SELECT MAX(d.month_start) AS last_month
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    WHERE f.line_type = 'sale'
),
activity AS (
    SELECT DISTINCT
        c.cohort_month,
        f.customer_id,
        (
            (d.year - EXTRACT(YEAR FROM c.cohort_month)) * 12
            + d.month - EXTRACT(MONTH FROM c.cohort_month)
        )::int AS period_index
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    JOIN analytics.dim_customer AS c USING (customer_id)
    WHERE f.line_type = 'sale'
),
observed AS (
    SELECT cohort_month, period_index, COUNT(*) AS active_customers
    FROM activity
    GROUP BY cohort_month, period_index
),
cohort_periods AS (
    SELECT
        o.cohort_month,
        o.active_customers AS cohort_size,
        p.period_index
    FROM observed AS o
    CROSS JOIN bounds AS b
    CROSS JOIN LATERAL GENERATE_SERIES(
        0,
        (
            (EXTRACT(YEAR FROM b.last_month) - EXTRACT(YEAR FROM o.cohort_month)) * 12
            + EXTRACT(MONTH FROM b.last_month) - EXTRACT(MONTH FROM o.cohort_month)
        )::int
    ) AS p (period_index)
    WHERE o.period_index = 0
)
SELECT
    cp.period_index,
    COUNT(*)                                                                    AS cohorts,
    ROUND(SUM(COALESCE(o.active_customers, 0))::numeric / SUM(cp.cohort_size), 4) AS retention_rate
FROM cohort_periods AS cp
LEFT JOIN observed AS o USING (cohort_month, period_index)
GROUP BY cp.period_index
ORDER BY cp.period_index;
