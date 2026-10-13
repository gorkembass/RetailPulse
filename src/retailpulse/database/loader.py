from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from retailpulse.cleaning.rules import OUTPUT_COLUMNS
from retailpulse.database.connection import driver_cursor, run_script

logger = logging.getLogger(__name__)

SCHEMA_SCRIPTS = ("01_staging.sql", "02_analytics.sql", "03_indexes.sql")
PRODUCT_COLUMNS = ["stock_code", "description", "category"]


def _copy_rows(cursor, table: str, frame: pd.DataFrame, columns: list[str]) -> None:
    records = frame[columns].astype(object).where(frame[columns].notna(), None)
    statement = f"COPY {table} ({', '.join(columns)}) FROM STDIN"
    with cursor.copy(statement) as copy:
        for row in records.itertuples(index=False, name=None):
            copy.write_row(row)


def load_warehouse(
    engine: Engine, transactions: pd.DataFrame, products: pd.DataFrame, schema_dir: Path
) -> dict[str, int]:
    """Rebuild the staging and analytics schemas from the processed layer.

    The load is a full refresh: the dataset is a fixed historical extract, so replacing the
    tables is simpler and safer than reconciling increments.
    """
    staging_ddl, analytics_ddl, indexes = (schema_dir / name for name in SCHEMA_SCRIPTS)

    run_script(engine, staging_ddl)
    with driver_cursor(engine) as cursor:
        _copy_rows(cursor, "staging.transactions", transactions, OUTPUT_COLUMNS)
        _copy_rows(cursor, "staging.products", products, PRODUCT_COLUMNS)
    logger.info("Loaded %d staging rows and %d products", len(transactions), len(products))

    run_script(engine, analytics_ddl)
    run_script(engine, indexes)

    counts = table_counts(engine)
    logger.info("Warehouse row counts: %s", counts)
    return counts


def table_counts(engine: Engine) -> dict[str, int]:
    tables = (
        "staging.transactions",
        "staging.products",
        "analytics.dim_date",
        "analytics.dim_product",
        "analytics.dim_customer",
        "analytics.fact_sales",
    )
    counts = {}
    with driver_cursor(engine) as cursor:
        for table in tables:
            cursor.execute(f"SELECT COUNT(*) FROM {table}")
            counts[table] = cursor.fetchone()[0]
    return counts
