from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

COLUMN_MAP = {
    "InvoiceNo": "invoice_no",
    "StockCode": "stock_code",
    "Description": "description",
    "Quantity": "quantity",
    "InvoiceDate": "invoice_date",
    "UnitPrice": "unit_price",
    "CustomerID": "customer_id",
    "Country": "country",
}


class SchemaError(ValueError):
    pass


def standardise_columns(frame: pd.DataFrame) -> pd.DataFrame:
    """Rename source columns to snake_case and attach the 1-based source row number."""
    missing = [column for column in COLUMN_MAP if column not in frame.columns]
    if missing:
        raise SchemaError(f"Raw data is missing required columns: {', '.join(missing)}")
    renamed = frame[list(COLUMN_MAP)].rename(columns=COLUMN_MAP).reset_index(drop=True)
    renamed.insert(0, "source_row", renamed.index + 1)
    return renamed


def read_raw(path: Path) -> pd.DataFrame:
    """Read a raw source file without interpreting its values.

    Every column is loaded as text so that malformed values survive until the cleaning
    layer, where they are classified instead of being silently coerced.
    """
    suffix = path.suffix.lower()
    logger.info("Reading %s", path)
    if suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(path, dtype=object)
    elif suffix == ".csv":
        frame = pd.read_csv(path, dtype=object, keep_default_na=False, na_values=[""])
    else:
        raise ValueError(f"Unsupported raw file type: {path.suffix}")
    return standardise_columns(frame)
