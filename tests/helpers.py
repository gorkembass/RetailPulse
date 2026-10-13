from __future__ import annotations

import pandas as pd

from retailpulse.cleaning.rules import classify_transactions
from retailpulse.ingestion.reader import standardise_columns

DEFAULT_LINE = {
    "InvoiceNo": "536365",
    "StockCode": "10001",
    "Description": "RED RETROSPOT LUNCH BAG",
    "Quantity": 2,
    "InvoiceDate": "2023-01-10 10:00:00",
    "UnitPrice": 5.0,
    "CustomerID": 17850,
    "Country": "United Kingdom",
}


def make_raw(lines: list[dict]) -> pd.DataFrame:
    """Build a raw-layout frame from partial line definitions, filling unspecified fields."""
    frame = pd.DataFrame([{**DEFAULT_LINE, **line} for line in lines], columns=list(DEFAULT_LINE))
    return standardise_columns(frame.astype(object))


def classify(lines: list[dict]) -> pd.DataFrame:
    return classify_transactions(make_raw(lines))
