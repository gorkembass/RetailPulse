from __future__ import annotations

import pandas as pd
import pytest

from retailpulse.cleaning import rules
from retailpulse.cleaning.quality import build_quality_report
from tests.helpers import classify, make_raw


def test_valid_line_is_a_sale_with_computed_amount():
    result = classify([{"Quantity": 3, "UnitPrice": 2.5}]).iloc[0]

    assert result["line_type"] == rules.SALE
    assert pd.isna(result["exclusion_reason"])
    assert result["line_amount"] == pytest.approx(7.5)


def test_no_rows_are_dropped():
    lines = [{}, {"UnitPrice": 0}, {"StockCode": "POST"}, {"InvoiceNo": "C536366", "Quantity": -1}]

    result = classify(lines)

    assert len(result) == len(lines)
    assert result["source_row"].tolist() == [1, 2, 3, 4]


@pytest.mark.parametrize(
    ("line", "expected_reason"),
    [
        ({"UnitPrice": 0}, rules.NON_POSITIVE_PRICE),
        ({"UnitPrice": -11062.06, "StockCode": "10002"}, rules.NON_POSITIVE_PRICE),
        ({"Quantity": -5, "UnitPrice": 0}, rules.NON_POSITIVE_QUANTITY),
        ({"Quantity": 0}, rules.NON_POSITIVE_QUANTITY),
        ({"StockCode": "POST"}, rules.NON_PRODUCT),
        ({"StockCode": "bank charges"}, rules.NON_PRODUCT),
        ({"StockCode": "gift_0001_20"}, rules.NON_PRODUCT),
        ({"InvoiceNo": "A563186"}, rules.INVALID_INVOICE),
        ({"InvoiceNo": "12345"}, rules.INVALID_INVOICE),
        ({"InvoiceNo": "C536366", "Quantity": 4}, rules.INCONSISTENT_CANCELLATION),
        ({"InvoiceDate": "not a date"}, rules.INVALID_DATE),
        ({"InvoiceDate": "1899-12-31 00:00:00"}, rules.INVALID_DATE),
        ({"InvoiceDate": None}, rules.INVALID_DATE),
        ({"Quantity": "many"}, rules.INVALID_FIELD),
        ({"Quantity": 1.5}, rules.INVALID_FIELD),
        ({"UnitPrice": None}, rules.INVALID_FIELD),
        ({"StockCode": None}, rules.INVALID_FIELD),
        ({"InvoiceNo": "  "}, rules.INVALID_FIELD),
    ],
)
def test_invalid_lines_are_excluded_with_a_reason(line, expected_reason):
    result = classify([line]).iloc[0]

    assert result["line_type"] == rules.EXCLUDED
    assert result["exclusion_reason"] == expected_reason


def test_future_dates_are_invalid_relative_to_the_reference_date():
    raw = make_raw([{"InvoiceDate": "2023-01-10 10:00:00"}])

    result = rules.classify_transactions(raw, as_of=pd.Timestamp("2023-01-01"))

    assert result.loc[0, "exclusion_reason"] == rules.INVALID_DATE


def test_exclusion_reason_follows_rule_precedence():
    result = classify([{"StockCode": "POST", "UnitPrice": 0, "InvoiceDate": "bad"}]).iloc[0]

    assert result["exclusion_reason"] == rules.INVALID_DATE


def test_missing_customer_is_flagged_but_still_counted_as_a_sale():
    result = classify([{"CustomerID": None}]).iloc[0]

    assert result["line_type"] == rules.SALE
    assert not result["has_customer_id"]
    assert pd.isna(result["customer_id"])


def test_identifiers_are_normalised():
    result = classify(
        [
            {
                "InvoiceNo": 536365,
                "StockCode": "85123a",
                "CustomerID": 17850.0,
                "Description": " A   B ",
            }
        ]
    ).iloc[0]

    assert result["invoice_no"] == "536365"
    assert result["stock_code"] == "85123A"
    assert result["customer_id"] == 17850
    assert result["description"] == "A B"


def test_quality_report_accounts_for_every_row():
    result = classify(
        [{}, {"UnitPrice": 0}, {"StockCode": "POST"}, {"InvoiceNo": "C536366", "Quantity": -1}]
    )

    report = build_quality_report(result)

    assert report["line_type_summary"]["rows"].sum() == len(result)
    excluded = report["exclusion_summary"].set_index("exclusion_reason")["rows"]
    assert excluded[rules.NON_POSITIVE_PRICE] == 1
    assert excluded[rules.NON_PRODUCT] == 1
    assert excluded.sum() == (result["line_type"] == rules.EXCLUDED).sum()
