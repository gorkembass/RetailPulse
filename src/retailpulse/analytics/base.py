from __future__ import annotations

import numpy as np
import pandas as pd

from retailpulse.cleaning.rules import RETURN, SALE
from retailpulse.ingestion.reader import SchemaError

AMOUNT_DECIMALS = 4

REQUIRED_COLUMNS = (
    "invoice_no",
    "stock_code",
    "quantity",
    "invoice_date",
    "customer_id",
    "country",
    "line_amount",
    "line_type",
)


def validate(transactions: pd.DataFrame) -> None:
    missing = [column for column in REQUIRED_COLUMNS if column not in transactions.columns]
    if missing:
        raise SchemaError(f"Transactions are missing required columns: {', '.join(missing)}")


def sales(transactions: pd.DataFrame) -> pd.DataFrame:
    validate(transactions)
    return transactions[transactions["line_type"] == SALE]


def returns(transactions: pd.DataFrame) -> pd.DataFrame:
    validate(transactions)
    return transactions[transactions["line_type"] == RETURN]


def safe_divide(numerator, denominator):
    """Divide and return NaN instead of raising or yielding infinity when dividing by zero."""
    if isinstance(denominator, pd.Series):
        return numerator / denominator.where(denominator != 0)
    return numerator / denominator if denominator else np.nan


def round_amounts(amounts):
    """Round summed amounts to the source precision so that equal totals compare as equal.

    Floating-point sums of identical totals can differ in the last bits, which would make
    tie-breaking in rankings depend on row order rather than on the stated sort keys.
    """
    return amounts.round(AMOUNT_DECIMALS)


def month_start(dates: pd.Series) -> pd.Series:
    return dates.dt.to_period("M").dt.to_timestamp()


def orders(transactions: pd.DataFrame) -> pd.DataFrame:
    """Aggregate sale lines to one row per invoice."""
    sale_lines = sales(transactions)
    return (
        sale_lines.groupby("invoice_no", observed=True)
        .agg(
            order_date=("invoice_date", "min"),
            customer_id=("customer_id", "first"),
            country=("country", "first"),
            order_value=("line_amount", "sum"),
            units=("quantity", "sum"),
            lines=("stock_code", "size"),
        )
        .reset_index()
    )
