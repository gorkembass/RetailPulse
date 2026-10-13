from __future__ import annotations

import os
from pathlib import Path

import pandas as pd
import pytest

from retailpulse.cleaning.products import build_products
from retailpulse.cleaning.rules import classify_transactions
from retailpulse.ingestion.reader import standardise_columns
from retailpulse.ingestion.synthetic import generate_synthetic_transactions

REPO_ROOT = Path(__file__).resolve().parents[1]
SQL_DIR = REPO_ROOT / "sql"


@pytest.fixture(scope="session")
def synthetic_transactions() -> pd.DataFrame:
    raw = standardise_columns(generate_synthetic_transactions(seed=42))
    return classify_transactions(raw)


@pytest.fixture(scope="session")
def synthetic_products(synthetic_transactions: pd.DataFrame) -> pd.DataFrame:
    return build_products(synthetic_transactions)


@pytest.fixture(scope="session")
def database_engine():
    url = os.environ.get("RETAILPULSE_TEST_DATABASE_URL")
    if not url:
        pytest.skip("RETAILPULSE_TEST_DATABASE_URL is not set")
    from retailpulse.database.connection import get_engine

    engine = get_engine(url)
    yield engine
    engine.dispose()


@pytest.fixture(scope="session")
def warehouse(database_engine, synthetic_transactions, synthetic_products):
    from retailpulse.database.loader import load_warehouse

    load_warehouse(database_engine, synthetic_transactions, synthetic_products, SQL_DIR / "schema")
    return database_engine
