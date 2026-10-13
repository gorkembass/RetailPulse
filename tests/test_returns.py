from __future__ import annotations

import pytest

from retailpulse.analytics import sales
from retailpulse.cleaning import rules
from retailpulse.cleaning.quality import exclusion_summary
from tests.helpers import classify


def test_cancellation_with_negative_quantity_is_a_return():
    result = classify([{"InvoiceNo": "C536400", "Quantity": -3, "UnitPrice": 4.0}]).iloc[0]

    assert result["line_type"] == rules.RETURN
    assert result["is_cancellation"]
    assert result["line_amount"] == pytest.approx(-12.0)


def test_lowercase_cancellation_prefix_is_recognised():
    result = classify([{"InvoiceNo": "c536400", "Quantity": -1}]).iloc[0]

    assert result["line_type"] == rules.RETURN


def test_negative_quantity_without_cancellation_is_a_stock_adjustment_not_a_return():
    result = classify([{"Quantity": -40, "UnitPrice": 0, "Description": "damaged"}]).iloc[0]

    assert result["line_type"] == rules.EXCLUDED
    assert result["exclusion_reason"] == rules.NON_POSITIVE_QUANTITY


def test_cancelled_non_product_lines_are_not_treated_as_merchandise_returns():
    result = classify(
        [{"InvoiceNo": "C536400", "StockCode": "AMAZONFEE", "Quantity": -1, "UnitPrice": 17836.46}]
    ).iloc[0]

    assert result["exclusion_reason"] == rules.NON_PRODUCT


def test_returns_reduce_net_revenue_but_not_gross_revenue_or_orders():
    transactions = classify(
        [
            {"InvoiceNo": "536365", "Quantity": 10, "UnitPrice": 3.0},
            {"InvoiceNo": "C536400", "Quantity": -4, "UnitPrice": 3.0},
        ]
    )

    kpis = sales.kpi_summary(transactions)

    assert kpis["gross_revenue"] == pytest.approx(30.0)
    assert kpis["return_value"] == pytest.approx(12.0)
    assert kpis["net_revenue"] == pytest.approx(18.0)
    assert kpis["orders"] == 1
    assert kpis["units_sold"] == 10
    assert kpis["return_rate"] == pytest.approx(0.4)


def test_fully_reversed_order_nets_to_zero():
    transactions = classify(
        [
            {"InvoiceNo": "581483", "Quantity": 80995, "UnitPrice": 2.08},
            {"InvoiceNo": "C581484", "Quantity": -80995, "UnitPrice": 2.08},
        ]
    )

    assert sales.kpi_summary(transactions)["net_revenue"] == pytest.approx(0.0)


def test_exclusion_summary_reports_value_of_excluded_adjustments():
    transactions = classify(
        [
            {"InvoiceNo": "C536400", "StockCode": "M", "Quantity": -1, "UnitPrice": 100.0},
            {"StockCode": "POST", "Quantity": 1, "UnitPrice": 18.0},
        ]
    )

    summary = exclusion_summary(transactions).set_index("exclusion_reason")

    assert summary.loc[rules.NON_PRODUCT, "rows"] == 2
    assert summary.loc[rules.NON_PRODUCT, "line_amount"] == pytest.approx(-82.0)
