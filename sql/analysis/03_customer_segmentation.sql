-- Customer analysis: RFM segmentation, new versus returning buyers and value concentration.
-- Only orders with a customer ID can be attributed; see 06_data_quality.sql for coverage.

-- name: rfm_scores
-- Scoring and segment rules live in the analytics.v_customer_rfm view (sql/schema/02_analytics.sql).
SELECT
    customer_id,
    last_order_date,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    rfm_score,
    segment
FROM analytics.v_customer_rfm
ORDER BY customer_id;

-- name: rfm_segment_summary
SELECT
    segment,
    COUNT(*)                                                    AS customers,
    ROUND(COUNT(*)::numeric / SUM(COUNT(*)) OVER (), 4)         AS customer_share,
    SUM(monetary)                                               AS monetary,
    ROUND(SUM(monetary) / SUM(SUM(monetary)) OVER (), 4)        AS monetary_share,
    ROUND(AVG(recency_days), 1)                                 AS avg_recency_days,
    ROUND(AVG(frequency), 2)                                    AS avg_frequency,
    ROUND(AVG(monetary), 2)                                     AS avg_monetary
FROM analytics.v_customer_rfm
GROUP BY segment
ORDER BY monetary DESC;

-- name: new_vs_returning_by_month
WITH orders AS (
    SELECT
        o.invoice_no,
        o.customer_id,
        o.order_value,
        DATE_TRUNC('month', o.order_date)::date AS order_month,
        c.cohort_month
    FROM analytics.v_orders AS o
    LEFT JOIN analytics.dim_customer AS c USING (customer_id)
),
labelled AS (
    SELECT
        order_month,
        customer_id,
        order_value,
        CASE
            WHEN customer_id IS NULL        THEN 'unidentified'
            WHEN order_month = cohort_month THEN 'new'
            ELSE 'returning'
        END AS customer_type
    FROM orders
)
SELECT
    order_month                                                             AS period,
    customer_type,
    COUNT(DISTINCT customer_id)                                             AS customers,
    COUNT(*)                                                                AS orders,
    SUM(order_value)                                                        AS gross_revenue,
    ROUND(SUM(order_value) / SUM(SUM(order_value)) OVER (PARTITION BY order_month), 4)
                                                                            AS revenue_share
FROM labelled
GROUP BY order_month, customer_type
ORDER BY order_month, customer_type;

-- name: repeat_purchase_rate
SELECT
    COUNT(*)                                                            AS customers,
    COUNT(*) FILTER (WHERE order_count > 1)                             AS repeat_customers,
    ROUND(COUNT(*) FILTER (WHERE order_count > 1)::numeric / COUNT(*), 4) AS repeat_purchase_rate,
    ROUND(AVG(order_count), 2)                                          AS avg_orders_per_customer
FROM analytics.dim_customer
WHERE order_count > 0;

-- name: customer_value_deciles
WITH customer_revenue AS (
    SELECT
        customer_id,
        SUM(order_value) AS gross_revenue,
        COUNT(*)         AS orders
    FROM analytics.v_orders
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
),
deciled AS (
    SELECT
        *,
        NTILE(10) OVER (ORDER BY gross_revenue DESC, customer_id) AS value_decile
    FROM customer_revenue
)
SELECT
    value_decile,
    COUNT(*)                                                          AS customers,
    SUM(gross_revenue)                                                AS gross_revenue,
    ROUND(SUM(gross_revenue) / SUM(SUM(gross_revenue)) OVER (), 4)    AS gross_revenue_share,
    ROUND(AVG(gross_revenue), 2)                                      AS avg_revenue_per_customer,
    ROUND(AVG(orders), 2)                                             AS avg_orders_per_customer
FROM deciled
GROUP BY value_decile
ORDER BY value_decile;
