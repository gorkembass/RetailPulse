from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date

import pandas as pd
import streamlit as st

from retailpulse.config import Paths

MARKETS = ("All markets", "United Kingdom", "International")
HOME_MARKET = "United Kingdom"


@dataclass(frozen=True)
class Dataset:
    transactions: pd.DataFrame
    products: pd.DataFrame
    metadata: dict


@st.cache_data(show_spinner="Loading processed data")
def load_dataset() -> Dataset | None:
    paths = Paths()
    if not paths.transactions.exists() or not paths.products.exists():
        return None
    metadata = {}
    if paths.source_metadata.exists():
        metadata = json.loads(paths.source_metadata.read_text(encoding="utf-8"))
    return Dataset(
        transactions=pd.read_parquet(paths.transactions),
        products=pd.read_parquet(paths.products),
        metadata=metadata,
    )


@st.cache_data(show_spinner=False)
def filter_transactions(
    transactions: pd.DataFrame, start: date, end: date, market: str
) -> pd.DataFrame:
    dates = transactions["invoice_date"].dt.date
    selected = transactions[(dates >= start) & (dates <= end)]
    if market == HOME_MARKET:
        return selected[selected["country"] == HOME_MARKET]
    if market == "International":
        return selected[selected["country"] != HOME_MARKET]
    return selected
