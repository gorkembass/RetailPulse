-- Product and category performance, revenue concentration and return behaviour.
-- Categories are derived from product descriptions (see docs/data_quality.md).

-- name: product_performance
-- dim_product drives the query so that products with returns but no sales in the period
-- are kept; otherwise product totals would not reconcile with the headline return value.
WITH sold AS (
    SELECT
        stock_code,
        COUNT(DISTINCT invoice_no)  AS orders,
        SUM(quantity)               AS units_sold,
        SUM(line_amount)            AS gross_revenue
    FROM analytics.fact_sales
    WHERE line_type = 'sale'
    GROUP BY stock_code
),
refunded AS (
    SELECT
        stock_code,
        -SUM(quantity)     AS units_returned,
        -SUM(line_amount)  AS return_value
    FROM analytics.fact_sales
    WHERE line_type = 'return'
    GROUP BY stock_code
)
SELECT
    ROW_NUMBER() OVER (ORDER BY COALESCE(s.gross_revenue, 0) DESC, p.stock_code)  AS revenue_rank,
    p.stock_code,
    p.description,
    p.category,
    COALESCE(s.orders, 0)                                                 AS orders,
    COALESCE(s.units_sold, 0)                                             AS units_sold,
    COALESCE(s.gross_revenue, 0)                                          AS gross_revenue,
    COALESCE(r.units_returned, 0)                                         AS units_returned,
    COALESCE(r.return_value, 0)                                           AS return_value,
    COALESCE(s.gross_revenue, 0) - COALESCE(r.return_value, 0)            AS net_revenue,
    ROUND(COALESCE(r.return_value, 0) / NULLIF(s.gross_revenue, 0), 4)    AS return_rate,
    ROUND(
        SUM(COALESCE(s.gross_revenue, 0)) OVER (
            ORDER BY COALESCE(s.gross_revenue, 0) DESC, p.stock_code
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) / SUM(s.gross_revenue) OVER (),
        4
    )                                                                     AS cumulative_revenue_share
FROM analytics.dim_product AS p
LEFT JOIN sold AS s USING (stock_code)
LEFT JOIN refunded AS r USING (stock_code)
ORDER BY revenue_rank;

-- name: revenue_concentration
WITH product_revenue AS (
    SELECT
        stock_code,
        SUM(line_amount) AS gross_revenue
    FROM analytics.fact_sales
    WHERE line_type = 'sale'
    GROUP BY stock_code
),
ranked AS (
    SELECT
        gross_revenue,
        NTILE(10) OVER (ORDER BY gross_revenue DESC, stock_code) AS revenue_decile
    FROM product_revenue
)
SELECT
    revenue_decile,
    COUNT(*)                                                          AS products,
    SUM(gross_revenue)                                                AS gross_revenue,
    ROUND(SUM(gross_revenue) / SUM(SUM(gross_revenue)) OVER (), 4)    AS gross_revenue_share,
    ROUND(
        SUM(SUM(gross_revenue)) OVER (ORDER BY revenue_decile)
        / SUM(SUM(gross_revenue)) OVER (),
        4
    )                                                                 AS cumulative_revenue_share
FROM ranked
GROUP BY revenue_decile
ORDER BY revenue_decile;

-- name: category_performance
WITH lines AS (
    SELECT
        p.category,
        f.stock_code,
        f.line_type,
        f.quantity,
        f.line_amount
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_product AS p USING (stock_code)
)
SELECT
    category,
    COUNT(DISTINCT stock_code) FILTER (WHERE line_type = 'sale')                AS products,
    COALESCE(SUM(quantity) FILTER (WHERE line_type = 'sale'), 0)                AS units_sold,
    COALESCE(SUM(line_amount) FILTER (WHERE line_type = 'sale'), 0)             AS gross_revenue,
    COALESCE(-SUM(line_amount) FILTER (WHERE line_type = 'return'), 0)          AS return_value,
    SUM(line_amount)                                                            AS net_revenue,
    ROUND(
        COALESCE(SUM(line_amount) FILTER (WHERE line_type = 'sale'), 0)
        / SUM(SUM(line_amount) FILTER (WHERE line_type = 'sale')) OVER (),
        4
    )                                                                           AS gross_revenue_share,
    ROUND(
        COALESCE(-SUM(line_amount) FILTER (WHERE line_type = 'return'), 0)
        / NULLIF(SUM(line_amount) FILTER (WHERE line_type = 'sale'), 0),
        4
    )                                                                           AS return_rate
FROM lines
GROUP BY category
ORDER BY gross_revenue DESC, category;

-- name: category_monthly_leaders
WITH monthly AS (
    SELECT
        d.month_start,
        p.category,
        SUM(f.line_amount) AS gross_revenue
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    JOIN analytics.dim_product AS p USING (stock_code)
    WHERE f.line_type = 'sale'
    GROUP BY d.month_start, p.category
),
ranked AS (
    SELECT
        month_start,
        category,
        gross_revenue,
        ROUND(gross_revenue / SUM(gross_revenue) OVER (PARTITION BY month_start), 4) AS month_share,
        DENSE_RANK() OVER (PARTITION BY month_start ORDER BY gross_revenue DESC)     AS category_rank
    FROM monthly
)
SELECT month_start, category, gross_revenue, month_share, category_rank
FROM ranked
WHERE category_rank <= 3
ORDER BY month_start, category_rank;

-- name: most_returned_products
-- Limited to products with meaningful sales so that tiny denominators do not dominate.
WITH product_totals AS (
    SELECT
        stock_code,
        SUM(line_amount) FILTER (WHERE line_type = 'sale')                    AS gross_revenue,
        SUM(quantity) FILTER (WHERE line_type = 'sale')                       AS units_sold,
        COALESCE(-SUM(line_amount) FILTER (WHERE line_type = 'return'), 0)    AS return_value,
        COALESCE(-SUM(quantity) FILTER (WHERE line_type = 'return'), 0)       AS units_returned
    FROM analytics.fact_sales
    GROUP BY stock_code
)
SELECT
    t.stock_code,
    p.description,
    p.category,
    t.gross_revenue,
    t.return_value,
    t.units_sold,
    t.units_returned,
    ROUND(t.return_value / t.gross_revenue, 4) AS return_rate
FROM product_totals AS t
JOIN analytics.dim_product AS p USING (stock_code)
WHERE t.gross_revenue >= 1000
  AND t.return_value > 0
ORDER BY return_rate DESC, t.return_value DESC
LIMIT 20;
