-- Analytics layer: a star schema built only from valid sale and return lines.
-- fact_sales.line_amount is signed: positive for sales, negative for returns.

CREATE SCHEMA IF NOT EXISTS analytics;

DROP TABLE IF EXISTS analytics.fact_sales CASCADE;
DROP TABLE IF EXISTS analytics.dim_customer CASCADE;
DROP TABLE IF EXISTS analytics.dim_product CASCADE;
DROP TABLE IF EXISTS analytics.dim_date CASCADE;

CREATE TABLE analytics.dim_date AS
SELECT
    d::date                                   AS date_key,
    EXTRACT(YEAR FROM d)::int                 AS year,
    EXTRACT(QUARTER FROM d)::int              AS quarter,
    EXTRACT(MONTH FROM d)::int                AS month,
    DATE_TRUNC('month', d)::date              AS month_start,
    TO_CHAR(d, 'FMMonth')                     AS month_name,
    TO_CHAR(d, 'YYYY-MM')                     AS year_month,
    EXTRACT(ISOYEAR FROM d)::int              AS iso_year,
    EXTRACT(WEEK FROM d)::int                 AS iso_week,
    EXTRACT(ISODOW FROM d)::int               AS iso_weekday,
    TO_CHAR(d, 'FMDay')                       AS day_name,
    EXTRACT(ISODOW FROM d) IN (6, 7)          AS is_weekend
FROM (
    SELECT MIN(invoice_date)::date AS first_day, MAX(invoice_date)::date AS last_day
    FROM staging.transactions
    WHERE line_type <> 'excluded'
) AS bounds
CROSS JOIN LATERAL GENERATE_SERIES(
    bounds.first_day::timestamp, bounds.last_day::timestamp, INTERVAL '1 day'
) AS d;

ALTER TABLE analytics.dim_date ADD PRIMARY KEY (date_key);

CREATE TABLE analytics.dim_product AS
SELECT
    stock_code,
    COALESCE(description, 'UNKNOWN') AS description,
    category
FROM staging.products;

ALTER TABLE analytics.dim_product ADD PRIMARY KEY (stock_code);

CREATE TABLE analytics.dim_customer AS
WITH valid_lines AS (
    SELECT customer_id, country, invoice_no, invoice_date, line_type
    FROM staging.transactions
    WHERE line_type <> 'excluded'
      AND customer_id IS NOT NULL
),
country_rank AS (
    SELECT
        customer_id,
        country,
        ROW_NUMBER() OVER (
            PARTITION BY customer_id
            ORDER BY COUNT(*) DESC, country
        ) AS preference
    FROM valid_lines
    GROUP BY customer_id, country
),
activity AS (
    SELECT
        customer_id,
        MIN(invoice_date) FILTER (WHERE line_type = 'sale')::date        AS first_order_date,
        MAX(invoice_date) FILTER (WHERE line_type = 'sale')::date        AS last_order_date,
        COUNT(DISTINCT invoice_no) FILTER (WHERE line_type = 'sale')     AS order_count
    FROM valid_lines
    GROUP BY customer_id
)
SELECT
    a.customer_id,
    c.country,
    a.first_order_date,
    DATE_TRUNC('month', a.first_order_date)::date AS cohort_month,
    a.last_order_date,
    a.order_count
FROM activity AS a
JOIN country_rank AS c
    ON c.customer_id = a.customer_id
   AND c.preference = 1;

ALTER TABLE analytics.dim_customer ADD PRIMARY KEY (customer_id);

CREATE TABLE analytics.fact_sales (
    source_row    bigint PRIMARY KEY,
    invoice_no    text NOT NULL,
    invoice_date  timestamp NOT NULL,
    date_key      date NOT NULL REFERENCES analytics.dim_date (date_key),
    stock_code    text NOT NULL REFERENCES analytics.dim_product (stock_code),
    customer_id   bigint REFERENCES analytics.dim_customer (customer_id),
    country       text NOT NULL,
    line_type     text NOT NULL CHECK (line_type IN ('sale', 'return')),
    quantity      bigint NOT NULL,
    unit_price    numeric(14, 4) NOT NULL CHECK (unit_price > 0),
    line_amount   numeric(18, 4) NOT NULL,
    CONSTRAINT amount_sign_matches_line_type
        CHECK ((line_type = 'sale' AND quantity > 0) OR (line_type = 'return' AND quantity < 0))
);

INSERT INTO analytics.fact_sales
SELECT
    source_row,
    invoice_no,
    invoice_date,
    invoice_date::date,
    stock_code,
    customer_id,
    COALESCE(country, 'Unspecified'),
    line_type,
    quantity,
    unit_price,
    line_amount
FROM staging.transactions
WHERE line_type <> 'excluded';

CREATE OR REPLACE VIEW analytics.v_orders AS
SELECT
    invoice_no,
    MIN(invoice_date)               AS order_date,
    MIN(date_key)                   AS date_key,
    MIN(customer_id)                AS customer_id,
    MIN(country)                    AS country,
    SUM(line_amount)                AS order_value,
    SUM(quantity)                   AS units,
    COUNT(*)                        AS lines
FROM analytics.fact_sales
WHERE line_type = 'sale'
GROUP BY invoice_no;

-- RFM scores per identified customer.
-- Scores are 1-5 from the share of customers ranked strictly below, so ties share a score:
--   score = 5 * (RANK() - 1) / COUNT(*) + 1   (integer division)
-- Recency is ranked descending because fewer days since the last order is better.
CREATE OR REPLACE VIEW analytics.v_customer_rfm AS
WITH snapshot AS (
    SELECT MAX(date_key) + 1 AS snapshot_date
    FROM analytics.fact_sales
    WHERE line_type = 'sale'
),
customer_metrics AS (
    SELECT
        customer_id,
        MAX(date_key) FILTER (WHERE line_type = 'sale')                 AS last_order_date,
        COUNT(DISTINCT invoice_no) FILTER (WHERE line_type = 'sale')    AS frequency,
        SUM(line_amount)                                                AS monetary
    FROM analytics.fact_sales
    WHERE customer_id IS NOT NULL
    GROUP BY customer_id
    HAVING COUNT(*) FILTER (WHERE line_type = 'sale') > 0
),
ranked AS (
    SELECT
        m.customer_id,
        m.last_order_date,
        s.snapshot_date - m.last_order_date                             AS recency_days,
        m.frequency,
        m.monetary,
        COUNT(*) OVER ()                                                AS customer_count,
        RANK() OVER (ORDER BY s.snapshot_date - m.last_order_date DESC) AS recency_rank,
        RANK() OVER (ORDER BY m.frequency)                              AS frequency_rank,
        RANK() OVER (ORDER BY m.monetary)                               AS monetary_rank
    FROM customer_metrics AS m
    CROSS JOIN snapshot AS s
),
scored AS (
    SELECT
        customer_id,
        last_order_date,
        recency_days,
        frequency,
        monetary,
        (5 * (recency_rank - 1) / customer_count + 1)::int              AS r_score,
        (5 * (frequency_rank - 1) / customer_count + 1)::int            AS f_score,
        (5 * (monetary_rank - 1) / customer_count + 1)::int             AS m_score
    FROM ranked
)
SELECT
    customer_id,
    last_order_date,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    CONCAT(r_score, f_score, m_score) AS rfm_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 4            THEN 'Champions'
        WHEN r_score = 3  AND f_score >= 4            THEN 'Loyal Customers'
        WHEN r_score <= 2 AND f_score >= 4            THEN 'At Risk'
        WHEN r_score >= 4 AND f_score BETWEEN 2 AND 3 THEN 'Potential Loyalists'
        WHEN r_score = 3  AND f_score BETWEEN 2 AND 3 THEN 'Needs Attention'
        WHEN r_score <= 2 AND f_score BETWEEN 2 AND 3 THEN 'Hibernating'
        WHEN r_score >= 4 AND f_score = 1             THEN 'New Customers'
        WHEN r_score = 3  AND f_score = 1             THEN 'Promising'
        ELSE 'Lost'
    END AS segment
FROM scored;

COMMENT ON TABLE analytics.fact_sales IS
    'One row per valid sale or return line. line_amount is negative for returns.';
COMMENT ON VIEW analytics.v_orders IS
    'One row per sale invoice. Returns are excluded; they are separate credit-note invoices.';
