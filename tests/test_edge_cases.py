from __future__ import annotations

import math

import pandas as pd
import pytest

from retailpulse.analytics import cohorts, customers, products, sales
from retailpulse.cleaning.products import build_products, categorise
from retailpulse.cleaning.quality import build_quality_report
from retailpulse.cleaning.rules import classify_transactions
from retailpulse.ingestion.reader import SchemaError, read_raw, standardise_columns
from retailpulse.pipeline import build_analytics
from tests.helpers import DEFAULT_LINE, classify, make_raw


@pytest.fixture
def empty_transactions() -> pd.DataFrame:
    return classify_transactions(make_raw([]))


def test_empty_input_is_classified_without_error(empty_transactions):
    assert empty_transactions.empty
    assert "line_type" in empty_transactions.columns


def test_empty_input_produces_zero_kpis(empty_transactions):
    kpis = sales.kpi_summary(empty_transactions)

    assert kpis["gross_revenue"] == 0
    assert kpis["orders"] == 0
    assert math.isnan(kpis["average_order_value"])
    assert math.isnan(kpis["return_rate"])


def test_every_analysis_handles_empty_input(empty_transactions):
    tables = build_analytics(empty_transactions, build_products(empty_transactions))

    empty_by_design = set(tables) - {"kpi_summary", "margin_scenarios"}
    assert all(tables[name].empty for name in empty_by_design)


def test_quality_report_handles_empty_input(empty_transactions):
    report = build_quality_report(empty_transactions)

    assert report["line_type_summary"]["rows"].sum() == 0
    assert report["exclusion_summary"]["rows"].sum() == 0


def test_data_with_only_excluded_rows_yields_no_customers():
    transactions = classify([{"UnitPrice": 0}, {"StockCode": "POST"}])

    assert customers.rfm_scores(transactions).empty
    assert cohorts.cohort_retention(transactions).empty
    assert sales.revenue_trend(transactions).empty


def test_data_without_any_customer_ids_still_reports_revenue():
    transactions = classify([{"CustomerID": None}, {"CustomerID": None, "InvoiceNo": "536366"}])

    assert sales.kpi_summary(transactions)["gross_revenue"] == pytest.approx(20.0)
    assert customers.rfm_scores(transactions).empty
    assert math.isnan(customers.repeat_purchase_rate(transactions))


@pytest.mark.parametrize("missing", ["InvoiceNo", "Quantity", "UnitPrice", "CustomerID"])
def test_missing_raw_column_is_reported(missing):
    frame = pd.DataFrame([DEFAULT_LINE]).drop(columns=[missing])

    with pytest.raises(SchemaError, match=missing):
        standardise_columns(frame)


def test_cleaning_requires_standardised_columns():
    with pytest.raises(SchemaError, match="source_row"):
        classify_transactions(pd.DataFrame([DEFAULT_LINE]))


def test_analytics_reject_frames_without_classification():
    unclassified = make_raw([{}])

    with pytest.raises(SchemaError, match="line_type"):
        sales.kpi_summary(unclassified)


def test_unsupported_raw_file_type_is_rejected(tmp_path):
    path = tmp_path / "data.json"
    path.write_text("{}")

    with pytest.raises(ValueError, match="Unsupported raw file type"):
        read_raw(path)


def test_raw_csv_values_are_not_coerced_on_read(tmp_path):
    path = tmp_path / "raw.csv"
    pd.DataFrame([{**DEFAULT_LINE, "Quantity": "abc", "CustomerID": ""}]).to_csv(path, index=False)

    raw = read_raw(path)

    assert raw.loc[0, "quantity"] == "abc"
    assert pd.isna(raw.loc[0, "customer_id"])


def test_products_without_description_fall_back_to_other():
    transactions = classify([{"Description": None}])

    product_table = build_products(transactions)

    assert product_table.loc[0, "category"] == "Other"
    assert products.product_performance(transactions, product_table).loc[0, "gross_revenue"] == 10


@pytest.mark.parametrize(
    ("description", "expected"),
    [
        ("RED RETROSPOT LUNCH BAG", "Bags & Storage"),
        ("VINTAGE CHRISTMAS BUNTING", "Seasonal & Party"),
        ("CERAMIC TEA MUG BLUE", "Kitchen & Dining"),
        ("SILVER HEART NECKLACE", "Fashion & Accessories"),
        ("EARRINGS", "Fashion & Accessories"),
        ("SPRING COLLECTION", "Other"),
        (None, "Other"),
    ],
)
def test_category_keywords_match_whole_words(description, expected):
    assert categorise(description) == expected
