-- Revenue trends: monthly and daily series, seasonality and the effect of returns over time.
-- Returns are dated by the credit note, because the source does not link them to a sale.

-- name: monthly_revenue_trend
WITH monthly AS (
    SELECT
        d.month_start                                                            AS period,
        COUNT(DISTINCT f.invoice_no) FILTER (WHERE f.line_type = 'sale')         AS orders,
        COUNT(DISTINCT d.date_key) FILTER (WHERE f.line_type = 'sale')           AS trading_days,
        COALESCE(SUM(f.line_amount) FILTER (WHERE f.line_type = 'sale'), 0)      AS gross_revenue,
        COALESCE(-SUM(f.line_amount) FILTER (WHERE f.line_type = 'return'), 0)   AS return_value
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    GROUP BY d.month_start
)
SELECT
    period,
    orders,
    trading_days,
    gross_revenue,
    return_value,
    gross_revenue - return_value                                                 AS net_revenue,
    ROUND(gross_revenue / NULLIF(orders, 0), 2)                                  AS average_order_value,
    ROUND(return_value / NULLIF(gross_revenue, 0), 4)                            AS return_rate,
    ROUND(gross_revenue / NULLIF(trading_days, 0), 2)                            AS gross_revenue_per_trading_day,
    ROUND(
        gross_revenue / NULLIF(LAG(gross_revenue) OVER (ORDER BY period), 0) - 1,
        4
    )                                                                            AS gross_revenue_growth,
    SUM(gross_revenue) OVER (ORDER BY period)                                    AS cumulative_gross_revenue
FROM monthly
ORDER BY period;

-- name: daily_revenue_trend
-- dim_date supplies every calendar day, so non-trading days appear as zero rather than as gaps
-- and the seven-day window always spans seven calendar days.
WITH daily AS (
    SELECT
        d.date_key                                                               AS period,
        d.iso_weekday,
        COUNT(DISTINCT f.invoice_no) FILTER (WHERE f.line_type = 'sale')         AS orders,
        COALESCE(SUM(f.line_amount) FILTER (WHERE f.line_type = 'sale'), 0)      AS gross_revenue,
        COALESCE(-SUM(f.line_amount) FILTER (WHERE f.line_type = 'return'), 0)   AS return_value
    FROM analytics.dim_date AS d
    LEFT JOIN analytics.fact_sales AS f USING (date_key)
    GROUP BY d.date_key, d.iso_weekday
)
SELECT
    period,
    iso_weekday,
    orders,
    gross_revenue,
    return_value,
    gross_revenue - return_value                                                 AS net_revenue,
    ROUND(
        AVG(gross_revenue) OVER (ORDER BY period ROWS BETWEEN 6 PRECEDING AND CURRENT ROW),
        2
    )                                                                            AS gross_revenue_7d_avg
FROM daily
ORDER BY period;

-- name: weekday_hour_pattern
SELECT
    EXTRACT(ISODOW FROM invoice_date)::int   AS iso_weekday,
    EXTRACT(HOUR FROM invoice_date)::int     AS hour,
    COUNT(DISTINCT invoice_no)               AS orders,
    SUM(line_amount)                         AS gross_revenue
FROM analytics.fact_sales
WHERE line_type = 'sale'
GROUP BY 1, 2
ORDER BY 1, 2;

-- name: best_and_worst_days
WITH daily AS (
    SELECT
        date_key,
        SUM(line_amount)            AS gross_revenue,
        COUNT(DISTINCT invoice_no)  AS orders
    FROM analytics.fact_sales
    WHERE line_type = 'sale'
    GROUP BY date_key
),
ranked AS (
    SELECT
        *,
        ROW_NUMBER() OVER (ORDER BY gross_revenue DESC) AS best_rank,
        ROW_NUMBER() OVER (ORDER BY gross_revenue)      AS worst_rank
    FROM daily
)
SELECT
    CASE WHEN best_rank <= 5 THEN 'best' ELSE 'worst' END AS day_group,
    date_key,
    TO_CHAR(date_key, 'FMDay')                            AS day_name,
    orders,
    gross_revenue
FROM ranked
WHERE best_rank <= 5 OR worst_rank <= 5
ORDER BY gross_revenue DESC;

-- name: returns_impact_by_month
-- Splits the gap between gross and net revenue and shows how much of it comes from the
-- largest single credit note, which separates systemic returns from one-off reversals.
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
),
monthly_sales AS (
    SELECT
        d.month_start,
        SUM(f.line_amount) AS gross_revenue
    FROM analytics.fact_sales AS f
    JOIN analytics.dim_date AS d USING (date_key)
    WHERE f.line_type = 'sale'
    GROUP BY d.month_start
)
SELECT
    s.month_start                                                               AS period,
    s.gross_revenue,
    COALESCE(r.credit_notes, 0)                                                 AS credit_notes,
    COALESCE(r.return_value, 0)                                                 AS return_value,
    ROUND(COALESCE(r.return_value, 0) / s.gross_revenue, 4)                     AS return_rate,
    COALESCE(r.largest_credit_note, 0)                                          AS largest_credit_note,
    ROUND(
        (COALESCE(r.return_value, 0) - COALESCE(r.largest_credit_note, 0)) / s.gross_revenue,
        4
    )                                                                           AS return_rate_excl_largest
FROM monthly_sales AS s
LEFT JOIN monthly_returns AS r USING (month_start)
ORDER BY s.month_start;
