-- Sales overview: headline KPIs, geography, order-size mix and the revenue-to-margin gap.
-- Source: analytics.fact_sales (valid sale and return lines only).

-- name: headline_kpis
WITH sales AS (
    SELECT
        SUM(line_amount)                                              AS gross_revenue,
        SUM(quantity)                                                 AS units_sold,
        COUNT(DISTINCT invoice_no)                                    AS orders,
        COUNT(DISTINCT customer_id)                                   AS customers,
        SUM(line_amount) FILTER (WHERE customer_id IS NOT NULL)       AS identified_revenue
    FROM analytics.fact_sales
    WHERE line_type = 'sale'
),
refunds AS (
    SELECT
        COALESCE(-SUM(line_amount), 0)                                AS return_value,
        COUNT(DISTINCT invoice_no)                                    AS return_invoices
    FROM analytics.fact_sales
    WHERE line_type = 'return'
),
order_values AS (
    SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY order_value)   AS median_order_value
    FROM analytics.v_orders
)
SELECT
    s.gross_revenue,
    r.return_value,
    s.gross_revenue - r.return_value                                  AS net_revenue,
    s.orders,
    r.return_invoices,
    s.customers,
    s.units_sold,
    ROUND(s.gross_revenue / NULLIF(s.orders, 0), 2)                   AS average_order_value,
    ROUND(o.median_order_value::numeric, 2)                           AS median_order_value,
    ROUND(r.return_value / NULLIF(s.gross_revenue, 0), 4)             AS return_rate,
    ROUND(s.identified_revenue / NULLIF(s.gross_revenue, 0), 4)       AS identified_revenue_share
FROM sales AS s
CROSS JOIN refunds AS r
CROSS JOIN order_values AS o;

-- name: revenue_by_country
WITH sold AS (
    SELECT
        country,
        COUNT(DISTINCT invoice_no)   AS orders,
        COUNT(DISTINCT customer_id)  AS customers,
        SUM(line_amount)             AS gross_revenue
    FROM analytics.fact_sales
    WHERE line_type = 'sale'
    GROUP BY country
),
refunded AS (
    SELECT country, -SUM(line_amount) AS return_value
    FROM analytics.fact_sales
    WHERE line_type = 'return'
    GROUP BY country
)
SELECT
    s.country,
    s.orders,
    s.customers,
    s.gross_revenue,
    COALESCE(r.return_value, 0)                                               AS return_value,
    s.gross_revenue - COALESCE(r.return_value, 0)                             AS net_revenue,
    ROUND(s.gross_revenue / s.orders, 2)                                      AS average_order_value,
    ROUND(s.gross_revenue / SUM(s.gross_revenue) OVER (), 4)                  AS gross_revenue_share,
    ROUND(COALESCE(r.return_value, 0) / NULLIF(s.gross_revenue, 0), 4)        AS return_rate,
    RANK() OVER (ORDER BY s.gross_revenue DESC)                               AS revenue_rank
FROM sold AS s
LEFT JOIN refunded AS r USING (country)
ORDER BY s.gross_revenue DESC, s.country;

-- name: domestic_vs_international
SELECT
    CASE WHEN country = 'United Kingdom' THEN 'Domestic (UK)' ELSE 'International' END AS market,
    COUNT(*)                                                    AS orders,
    COUNT(DISTINCT customer_id)                                 AS customers,
    SUM(order_value)                                            AS gross_revenue,
    ROUND(AVG(order_value), 2)                                  AS average_order_value,
    ROUND(SUM(order_value) / SUM(SUM(order_value)) OVER (), 4)  AS gross_revenue_share
FROM analytics.v_orders
GROUP BY 1
ORDER BY gross_revenue DESC;

-- name: order_value_distribution
WITH bucketed AS (
    SELECT
        order_value,
        CASE
            WHEN order_value < 50    THEN 1
            WHEN order_value < 150   THEN 2
            WHEN order_value < 300   THEN 3
            WHEN order_value < 500   THEN 4
            WHEN order_value < 1000  THEN 5
            WHEN order_value < 5000  THEN 6
            ELSE 7
        END AS bucket_order
    FROM analytics.v_orders
)
SELECT
    bucket_order,
    CASE bucket_order
        WHEN 1 THEN 'Under 50'
        WHEN 2 THEN '50 to 149'
        WHEN 3 THEN '150 to 299'
        WHEN 4 THEN '300 to 499'
        WHEN 5 THEN '500 to 999'
        WHEN 6 THEN '1,000 to 4,999'
        ELSE '5,000 and above'
    END                                                         AS order_value_band,
    COUNT(*)                                                    AS orders,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER (), 4)         AS order_share,
    SUM(order_value)                                            AS gross_revenue,
    ROUND(SUM(order_value) / SUM(SUM(order_value)) OVER (), 4)  AS gross_revenue_share
FROM bucketed
GROUP BY bucket_order
ORDER BY bucket_order;

-- name: revenue_vs_assumed_margin
-- The source has no cost data. The COGS ratios below are assumptions used to show how far
-- revenue can sit from profit; the output is a scenario table, not measured profitability.
WITH totals AS (
    SELECT
        SUM(line_amount) FILTER (WHERE line_type = 'sale')                    AS gross_revenue,
        COALESCE(-SUM(line_amount) FILTER (WHERE line_type = 'return'), 0)    AS return_value
    FROM analytics.fact_sales
),
scenarios (assumed_cogs_ratio) AS (
    VALUES (0.50), (0.60), (0.70)
)
SELECT
    s.assumed_cogs_ratio,
    t.gross_revenue,
    t.return_value,
    t.gross_revenue - t.return_value                                              AS net_revenue,
    ROUND((t.gross_revenue - t.return_value) * s.assumed_cogs_ratio, 2)           AS assumed_cogs,
    ROUND((t.gross_revenue - t.return_value) * (1 - s.assumed_cogs_ratio), 2)     AS assumed_gross_margin,
    ROUND(
        (t.gross_revenue - t.return_value) * (1 - s.assumed_cogs_ratio)
        / NULLIF(t.gross_revenue, 0),
        4
    )                                                                             AS assumed_margin_on_gross_revenue
FROM totals AS t
CROSS JOIN scenarios AS s
ORDER BY s.assumed_cogs_ratio;
