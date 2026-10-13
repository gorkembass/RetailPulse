from __future__ import annotations

import pandas as pd
import pytest

from retailpulse.analytics import customers
from tests.helpers import classify


def order(invoice: int, customer: int | None, date: str, amount: float) -> dict:
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
            order(600001, 1, "2023-01-05", 10),
            order(600002, 2, "2023-02-05", 20),
            order(600003, 2, "2023-02-06", 20),
            order(600004, 3, "2023-03-05", 30),
            order(600005, 3, "2023-03-06", 30),
            order(600006, 3, "2023-03-07", 30),
            order(600007, 4, "2023-04-05", 40),
            order(600008, 4, "2023-04-06", 40),
            order(600009, 4, "2023-04-07", 40),
            order(600010, 4, "2023-04-08", 40),
            order(600011, 5, "2023-05-05", 50),
            order(600012, 5, "2023-05-06", 50),
            order(600013, 5, "2023-05-07", 50),
            order(600014, 5, "2023-05-08", 50),
            order(600015, 5, "2023-05-09", 50),
            order(600016, None, "2023-05-10", 999),
        ]
    )


def test_rfm_metrics(transactions):
    rfm = customers.rfm_scores(transactions).set_index("customer_id")

    assert len(rfm) == 5
    assert rfm.loc[5, "recency_days"] == 2
    assert rfm.loc[1, "recency_days"] == 126
    assert rfm["frequency"].tolist() == [1, 2, 3, 4, 5]
    assert rfm["monetary"].tolist() == pytest.approx([10, 40, 90, 160, 250])


def test_scores_spread_across_quintiles_for_distinct_values(transactions):
    rfm = customers.rfm_scores(transactions).set_index("customer_id")

    assert rfm["r_score"].tolist() == [1, 2, 3, 4, 5]
    assert rfm["f_score"].tolist() == [1, 2, 3, 4, 5]
    assert rfm["m_score"].tolist() == [1, 2, 3, 4, 5]
    assert rfm.loc[5, "rfm_score"] == "555"


def test_segments(transactions):
    rfm = customers.rfm_scores(transactions).set_index("customer_id")

    assert rfm["segment"].to_dict() == {
        1: "Lost",
        2: "Hibernating",
        3: "Needs Attention",
        4: "Champions",
        5: "Champions",
    }


def test_snapshot_date_can_be_overridden(transactions):
    rfm = customers.rfm_scores(transactions, snapshot_date=pd.Timestamp("2023-06-01"))

    assert rfm.set_index("customer_id").loc[5, "recency_days"] == 23


def test_tied_values_share_a_score():
    scores = customers.percentile_score(pd.Series([1, 1, 1, 1, 7, 7, 9, 9, 9, 12]))

    assert scores.tolist() == [1, 1, 1, 1, 3, 3, 4, 4, 4, 5]


def test_identical_customers_all_receive_the_lowest_score():
    scores = customers.percentile_score(pd.Series([3, 3, 3]))

    assert scores.tolist() == [1, 1, 1]


def test_lower_recency_scores_higher():
    scores = customers.percentile_score(pd.Series([1, 50, 300]), higher_is_better=False)

    assert scores.tolist() == [4, 2, 1]


def test_monetary_is_net_of_returns():
    transactions = classify(
        [
            order(600001, 1, "2023-01-05", 100),
            {
                "InvoiceNo": "C600002",
                "CustomerID": 1,
                "Quantity": -1,
                "UnitPrice": 30,
                "InvoiceDate": "2023-01-09 10:00:00",
            },
        ]
    )

    rfm = customers.rfm_scores(transactions).iloc[0]

    assert rfm["monetary"] == pytest.approx(70.0)
    assert rfm["frequency"] == 1
    assert rfm["recency_days"] == 1


def test_customers_with_only_returns_are_not_scored():
    transactions = classify(
        [
            order(600001, 1, "2023-01-05", 100),
            {"InvoiceNo": "C600002", "CustomerID": 2, "Quantity": -1, "UnitPrice": 30},
        ]
    )

    assert customers.rfm_scores(transactions)["customer_id"].tolist() == [1]


@pytest.mark.parametrize(
    ("r_score", "f_score", "expected"),
    [
        (5, 5, "Champions"),
        (3, 4, "Loyal Customers"),
        (1, 5, "At Risk"),
        (4, 2, "Potential Loyalists"),
        (3, 3, "Needs Attention"),
        (2, 2, "Hibernating"),
        (5, 1, "New Customers"),
        (3, 1, "Promising"),
        (1, 1, "Lost"),
    ],
)
def test_segment_grid(r_score, f_score, expected):
    segment = customers.assign_segment(pd.Series([r_score]), pd.Series([f_score]))

    assert segment.iloc[0] == expected


def test_segment_summary_accounts_for_every_customer(transactions):
    rfm = customers.rfm_scores(transactions)

    summary = customers.rfm_segment_summary(rfm)

    assert summary["customers"].sum() == 5
    assert summary["customer_share"].sum() == pytest.approx(1.0)
    assert summary["monetary"].sum() == pytest.approx(550.0)


def test_new_vs_returning(transactions):
    extra = classify(
        [
            order(600001, 1, "2023-01-05", 10),
            order(600002, 1, "2023-01-20", 10),
            order(600003, 1, "2023-02-05", 30),
            order(600004, 2, "2023-02-06", 20),
            order(600005, None, "2023-02-07", 50),
        ]
    )

    table = customers.new_vs_returning(extra).set_index(["period", "customer_type"])

    january, february = pd.Timestamp("2023-01-01"), pd.Timestamp("2023-02-01")
    assert table.loc[(january, "new"), "customers"] == 1
    assert table.loc[(january, "new"), "orders"] == 2
    assert table.loc[(february, "new"), "gross_revenue"] == pytest.approx(20.0)
    assert table.loc[(february, "returning"), "gross_revenue"] == pytest.approx(30.0)
    assert table.loc[(february, "unidentified"), "revenue_share"] == pytest.approx(0.5)
    assert customers.repeat_purchase_rate(extra) == pytest.approx(0.5)
