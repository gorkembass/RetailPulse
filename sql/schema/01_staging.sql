-- Staging layer: every source row, typed and classified by the cleaning rules.
-- Nothing is filtered here so that data-quality queries can audit excluded records.

CREATE SCHEMA IF NOT EXISTS staging;

DROP TABLE IF EXISTS staging.transactions CASCADE;
CREATE TABLE staging.transactions (
    source_row        bigint PRIMARY KEY,
    invoice_no        text,
    stock_code        text,
    description       text,
    quantity          bigint,
    invoice_date      timestamp,
    unit_price        numeric(14, 4),
    customer_id       bigint,
    country           text,
    line_amount       numeric(18, 4),
    is_cancellation   boolean NOT NULL,
    is_duplicate      boolean NOT NULL,
    has_customer_id   boolean NOT NULL,
    line_type         text NOT NULL CHECK (line_type IN ('sale', 'return', 'excluded')),
    exclusion_reason  text,
    CONSTRAINT exclusion_reason_matches_line_type
        CHECK ((line_type = 'excluded') = (exclusion_reason IS NOT NULL))
);

DROP TABLE IF EXISTS staging.products CASCADE;
CREATE TABLE staging.products (
    stock_code   text PRIMARY KEY,
    description  text,
    category     text NOT NULL
);
