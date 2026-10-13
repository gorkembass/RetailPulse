from __future__ import annotations

from retailpulse.cleaning import rules
from retailpulse.cleaning.quality import duplicate_sensitivity
from tests.helpers import classify


def test_first_occurrence_is_kept_and_repeats_are_excluded():
    result = classify([{}, {}, {}])

    assert result["is_duplicate"].tolist() == [False, True, True]
    assert result["line_type"].tolist() == [rules.SALE, rules.EXCLUDED, rules.EXCLUDED]
    assert result["exclusion_reason"].tolist()[1:] == [rules.DUPLICATE, rules.DUPLICATE]


def test_lines_differing_in_any_business_field_are_not_duplicates():
    result = classify(
        [
            {},
            {"Quantity": 3},
            {"UnitPrice": 5.5},
            {"StockCode": "10002"},
            {"InvoiceNo": "536366"},
            {"CustomerID": 17851},
            {"InvoiceDate": "2023-01-10 10:01:00"},
        ]
    )

    assert not result["is_duplicate"].any()


def test_rows_with_missing_customer_can_be_duplicates():
    result = classify([{"CustomerID": None}, {"CustomerID": None}])

    assert result["is_duplicate"].tolist() == [False, True]


def test_whitespace_only_differences_are_duplicates():
    result = classify([{"Description": "LUNCH BAG"}, {"Description": "LUNCH BAG  "}])

    assert result["is_duplicate"].tolist() == [False, True]


def test_duplicated_returns_are_excluded_once():
    line = {"InvoiceNo": "C536400", "Quantity": -2}

    result = classify([line, line])

    assert result["line_type"].tolist() == [rules.RETURN, rules.EXCLUDED]


def test_duplicate_flag_is_reported_even_when_another_rule_takes_precedence():
    result = classify([{"StockCode": "POST"}, {"StockCode": "POST"}])

    assert result["is_duplicate"].tolist() == [False, True]
    assert result["exclusion_reason"].tolist() == [rules.NON_PRODUCT, rules.NON_PRODUCT]


def test_duplicate_sensitivity_reports_revenue_at_stake():
    result = classify([{"Quantity": 2, "UnitPrice": 5.0}] * 3)

    sensitivity = duplicate_sensitivity(result).set_index("scenario")["gross_revenue"]

    assert sensitivity["duplicates_excluded"] == 10.0
    assert sensitivity["duplicates_kept"] == 30.0
