from __future__ import annotations

import pandas as pd
import pytest

from retailpulse.analytics import cohorts
from tests.helpers import classify


def order(invoice: int, customer: int | None, date: str, amount: float = 10.0) -> dict:
    return {
        "InvoiceNo": str(invoice),
        "CustomerID": customer,
        "InvoiceDate": f"{date} 10:00:00",
        "Quantity": 1,
        "UnitPrice": amount,
    }


@pytest.fixture
def transactions() -> pd.DataFrame:
    return classify(
        [
            order(600001, 1, "2023-01-05"),
            order(600002, 1, "2023-01-25"),
            order(600003, 1, "2023-02-10"),
            order(600004, 1, "2023-03-10"),
            order(600005, 2, "2023-01-31"),
            order(600006, 2, "2023-03-01", amount=25.0),
            order(600007, 3, "2023-02-14"),
            order(600008, None, "2023-01-15"),
        ]
    )


def test_cohort_sizes_and_activity(transactions):
    table = cohorts.cohort_retention(transactions).set_index(["cohort_month", "period_index"])

    january, february = pd.Timestamp("2023-01-01"), pd.Timestamp("2023-02-01")
    assert table.loc[(january, 0), "cohort_size"] == 2
    assert table.loc[(january, 0), "active_customers"] == 2
    assert table.loc[(january, 1), "active_customers"] == 1
    assert table.loc[(january, 2), "active_customers"] == 2
    assert table.loc[(february, 0), "cohort_size"] == 1
    assert len(table) == 5


def test_observed_months_without_purchases_count_as_zero_retention(transactions):
    table = cohorts.cohort_retention(transactions).set_index(["cohort_month", "period_index"])

    february = pd.Timestamp("2023-02-01")
    assert table.loc[(february, 1), "active_customers"] == 0
    assert table.loc[(february, 1), "retention_rate"] == 0.0
    assert (february, 2) not in table.index


def test_retention_rates(transactions):
    table = cohorts.cohort_retention(transactions).set_index(["cohort_month", "period_index"])

    january = pd.Timestamp("2023-01-01")
    assert table.loc[(january, 0), "retention_rate"] == 1.0
    assert table.loc[(january, 1), "retention_rate"] == pytest.approx(0.5)
    assert table.loc[(january, 2), "retention_rate"] == pytest.approx(1.0)


def test_cohort_revenue(transactions):
    table = cohorts.cohort_retention(transactions).set_index(["cohort_month", "period_index"])

    january = pd.Timestamp("2023-01-01")
    assert table.loc[(january, 0), "gross_revenue"] == pytest.approx(30.0)
    assert table.loc[(january, 2), "gross_revenue"] == pytest.approx(35.0)


def test_period_index_spans_year_boundaries():
    transactions = classify([order(600001, 1, "2022-11-15"), order(600002, 1, "2023-02-15")])

    table = cohorts.cohort_retention(transactions)

    assert table["period_index"].tolist() == [0, 1, 2, 3]
    assert table["active_customers"].tolist() == [1, 0, 0, 1]


def test_returns_do_not_count_as_activity():
    transactions = classify(
        [
            order(600001, 1, "2023-01-05"),
            {
                "InvoiceNo": "C600002",
                "CustomerID": 1,
                "Quantity": -1,
                "UnitPrice": 10.0,
                "InvoiceDate": "2023-02-05 10:00:00",
            },
        ]
    )

    assert cohorts.cohort_retention(transactions)["active_customers"].tolist() == [1]


def test_retention_matrix_leaves_unobserved_periods_empty(transactions):
    matrix = cohorts.retention_matrix(cohorts.cohort_retention(transactions))

    assert matrix.shape == (2, 3)
    assert matrix.loc[pd.Timestamp("2023-02-01"), 1] == 0.0
    assert pd.isna(matrix.loc[pd.Timestamp("2023-02-01"), 2])


def test_average_retention_is_weighted_by_cohort_size(transactions):
    average = cohorts.average_retention(cohorts.cohort_retention(transactions)).set_index(
        "period_index"
    )

    assert average.loc[0, "retention_rate"] == 1.0
    assert average.loc[0, "cohorts"] == 2
    assert average.loc[1, "cohorts"] == 2
    assert average.loc[1, "retention_rate"] == pytest.approx(1 / 3)
    assert average.loc[2, "cohorts"] == 1
