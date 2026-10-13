from __future__ import annotations

import logging
from pathlib import Path

from sqlalchemy import Engine

from retailpulse.database.connection import driver_cursor

logger = logging.getLogger(__name__)

STAR_SCHEMA_EXPORTS = {
    "fact_sales": "analytics.fact_sales",
    "dim_date": "analytics.dim_date",
    "dim_product": "analytics.dim_product",
    "dim_customer": "analytics.dim_customer",
    "customer_rfm": "analytics.v_customer_rfm",
}


def export_star_schema(engine: Engine, output_dir: Path) -> list[Path]:
    """Write the analytics star schema to CSV files that Power BI can import directly."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    with driver_cursor(engine) as cursor:
        for name, relation in STAR_SCHEMA_EXPORTS.items():
            target = output_dir / f"{name}.csv"
            statement = f"COPY (SELECT * FROM {relation}) TO STDOUT WITH (FORMAT CSV, HEADER)"
            with target.open("wb") as handle, cursor.copy(statement) as copy:
                for chunk in copy:
                    handle.write(chunk)
            written.append(target)
            logger.info("Exported %s to %s", relation, target)
    return written
