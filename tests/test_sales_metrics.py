from __future__ import annotations

import pandas as pd
import pytest

from retailpulse.analytics import products, profitability, sales
from retailpulse.cleaning.products import build_products
from tests.helpers import classify

ORDERS = [
    {"InvoiceNo": "536365", "StockCode": "10001", "Quantity": 2, "UnitPrice": 5.0},
    {"InvoiceNo": "536365", "StockCode": "10002", "Quantity": 1, "UnitPrice": 20.0},
    {
        "InvoiceNo": "536366",
        "StockCode": "10001",
        "Quantity": 4,
        "UnitPrice": 5.0,
        "CustomerID": 17851,
        "Country": "France",
        "InvoiceDate": "2023-02-03 09:00:00",
    },
    {
        "InvoiceNo": "536367",
        "StockCode": "10002",
        "Quantity": 2,
        "UnitPrice": 20.0,
        "CustomerID": None,
        "InvoiceDate": "2023-02-04 09:00:00",
    },
    {
        "InvoiceNo": "C536368",
        "StockCode": "10001",
        "Quantity": -1,
        "UnitPrice": 5.0,
        "InvoiceDate": "2023-02-10 09:00:00",
    },
]


@pytest.fixture
def transactions() -> pd.DataFrame:
    return classify(ORDERS)


def test_revenue_kpis(transactions):
    kpis = sales.kpi_summary(transactions)

    assert kpis["gross_revenue"] == pytest.approx(90.0)
    assert kpis["return_value"] == pytest.approx(5.0)
    assert kpis["net_revenue"] == pytest.approx(85.0)
    assert kpis["orders"] == 3
    assert kpis["return_invoices"] == 1
    assert kpis["customers"] == 2
    assert kpis["units_sold"] == 9
    assert kpis["average_order_value"] == pytest.approx(30.0)
    assert kpis["median_order_value"] == pytest.approx(30.0)
    assert kpis["return_rate"] == pytest.approx(5 / 90)
    assert kpis["identified_revenue_share"] == pytest.approx(50 / 90)


def test_excluded_lines_do_not_contribute_to_revenue():
    with_noise = classify(
        [
            *ORDERS,
            {"InvoiceNo": "536369", "StockCode": "POST", "Quantity": 1, "UnitPrice": 18.0},
            {"InvoiceNo": "536370", "Quantity": 10, "UnitPrice": 0},
            ORDERS[0],
        ]
    )

    assert sales.kpi_summary(with_noise) == pytest.approx(sales.kpi_summary(classify(ORDERS)))


def test_monthly_trend_attributes_returns_to_the_credit_note_month(transactions):
    trend = sales.revenue_trend(transactions, "M").set_index("period")

    january, february = pd.Timestamp("2023-01-01"), pd.Timestamp("2023-02-01")
    assert trend.loc[january, "gross_revenue"] == pytest.approx(30.0)
    assert trend.loc[january, "return_value"] == 0
    assert trend.loc[february, "gross_revenue"] == pytest.approx(60.0)
    assert trend.loc[february, "return_value"] == pytest.approx(5.0)
    assert trend.loc[february, "net_revenue"] == pytest.approx(55.0)
    assert trend.loc[february, "orders"] == 2
    assert trend.loc[february, "gross_revenue_growth"] == pytest.approx(1.0)


def test_daily_trend_fills_non_trading_days_with_zero(transactions):
    trend = sales.revenue_trend(transactions, "D").set_index("period")

    assert len(trend) == 32
    assert trend.loc[pd.Timestamp("2023-01-11"), "gross_revenue"] == 0
    assert trend.loc[pd.Timestamp("2023-02-04"), "gross_revenue_7d_avg"] == pytest.approx(60 / 7)
    assert trend["gross_revenue"].sum() == pytest.approx(90.0)


def test_unsupported_trend_frequency_is_rejected(transactions):
    with pytest.raises(ValueError, match="Unsupported frequency"):
        sales.revenue_trend(transactions, "W")


def test_country_performance(transactions):
    table = sales.country_performance(transactions).set_index("country")

    assert table.index.tolist() == ["United Kingdom", "France"]
    assert table.loc["United Kingdom", "gross_revenue"] == pytest.approx(70.0)
    assert table.loc["United Kingdom", "net_revenue"] == pytest.approx(65.0)
    assert table.loc["France", "return_value"] == 0
    assert table["gross_revenue_share"].sum() == pytest.approx(1.0)


def test_product_performance_ranks_and_accumulates_share(transactions):
    table = products.product_performance(transactions, build_products(transactions))

    assert table["stock_code"].tolist() == ["10002", "10001"]
    assert table["gross_revenue"].tolist() == pytest.approx([60.0, 30.0])
    assert table["cumulative_revenue_share"].tolist() == pytest.approx([2 / 3, 1.0])
    assert table.loc[1, "units_returned"] == 1
    assert table.loc[1, "return_rate"] == pytest.approx(5 / 30)


def test_products_with_returns_but_no_sales_are_kept_so_totals_reconcile():
    transactions = classify(
        [
            {"InvoiceNo": "536365", "StockCode": "10001", "Quantity": 2, "UnitPrice": 5.0},
            {"InvoiceNo": "C536366", "StockCode": "10002", "Quantity": -1, "UnitPrice": 20.0},
        ]
    )
    product_table = build_products(transactions)

    by_product = products.product_performance(transactions, product_table).set_index("stock_code")
    by_category = products.category_performance(transactions, product_table)

    assert by_product.loc["10002", "gross_revenue"] == 0
    assert by_product.loc["10002", "units_returned"] == 1
    assert by_product["return_value"].sum() == pytest.approx(20.0)
    assert by_category["return_value"].sum() == pytest.approx(
        sales.kpi_summary(transactions)["return_value"]
    )
    assert by_category["products"].sum() == 1


def test_category_performance_totals_match_product_totals(transactions):
    product_table = build_products(transactions)

    categories = products.category_performance(transactions, product_table)

    assert categories["gross_revenue"].sum() == pytest.approx(90.0)
    assert categories["gross_revenue_share"].sum() == pytest.approx(1.0)


def test_margin_scenarios_are_derived_from_net_revenue():
    scenarios = profitability.margin_scenarios(100.0, 10.0, cogs_ratios=(0.6,)).iloc[0]

    assert scenarios["net_revenue"] == pytest.approx(90.0)
    assert scenarios["assumed_cogs"] == pytest.approx(54.0)
    assert scenarios["assumed_gross_margin"] == pytest.approx(36.0)
    assert scenarios["assumed_margin_on_gross_revenue"] == pytest.approx(0.36)


def test_margin_scenarios_reject_impossible_ratios():
    with pytest.raises(ValueError, match="between 0 and 1"):
        profitability.margin_scenarios(100.0, 0.0, cogs_ratios=(1.2,))


def test_weekday_hour_pattern_uses_iso_weekdays(transactions):
    pattern = sales.weekday_hour_pattern(transactions).set_index(["iso_weekday", "hour"])

    assert pattern.loc[(2, 10), "gross_revenue"] == pytest.approx(30.0)
    assert pattern.loc[(5, 9), "orders"] == 1
    assert pattern["gross_revenue"].sum() == pytest.approx(90.0)
