from __future__ import annotations

import numpy as np
import pandas as pd

from retailpulse.analytics.base import month_start, orders, returns, safe_divide, sales

SCORE_BINS = 5

RFM_COLUMNS = [
    "customer_id",
    "last_order_date",
    "recency_days",
    "frequency",
    "monetary",
    "r_score",
    "f_score",
    "m_score",
    "rfm_score",
    "segment",
]

SEGMENT_ORDER = [
    "Champions",
    "Loyal Customers",
    "At Risk",
    "Potential Loyalists",
    "Needs Attention",
    "Hibernating",
    "New Customers",
    "Promising",
    "Lost",
]


def percentile_score(values: pd.Series, higher_is_better: bool = True) -> pd.Series:
    """Score values 1-5 by the share of customers ranked strictly below them.

    Tied values always receive the same score, which NTILE-style quintiles do not guarantee.
    The SQL implementation uses the identical formula: ``5 * (RANK() - 1) / COUNT(*) + 1``.
    """
    rank = values.rank(method="min", ascending=higher_is_better).astype("int64")
    return (SCORE_BINS * (rank - 1)) // len(values) + 1


def assign_segment(r_score: pd.Series, f_score: pd.Series) -> pd.Series:
    """Map recency and frequency scores to a named segment on a 3x3 grid."""
    recent, cooling, inactive = r_score >= 4, r_score == 3, r_score <= 2
    frequent, occasional, single = f_score >= 4, f_score.between(2, 3), f_score == 1
    conditions = [
        recent & frequent,
        cooling & frequent,
        inactive & frequent,
        recent & occasional,
        cooling & occasional,
        inactive & occasional,
        recent & single,
        cooling & single,
        inactive & single,
    ]
    return pd.Series(
        np.select(conditions, SEGMENT_ORDER, default="Unclassified"), index=r_score.index
    )


def rfm_scores(
    transactions: pd.DataFrame, snapshot_date: pd.Timestamp | None = None
) -> pd.DataFrame:
    """Recency, frequency and monetary scores per identified customer.

    Recency is measured in whole days up to the day after the last sale in the data.
    Frequency counts sale invoices. Monetary is net of returns.
    """
    sale_lines = sales(transactions).dropna(subset=["customer_id"])
    if sale_lines.empty:
        return pd.DataFrame(columns=RFM_COLUMNS)

    if snapshot_date is None:
        snapshot_date = sales(transactions)["invoice_date"].max().normalize() + pd.Timedelta(days=1)

    purchased = sale_lines.groupby("customer_id").agg(
        last_order_date=("invoice_date", lambda dates: dates.max().normalize()),
        frequency=("invoice_no", "nunique"),
        gross=("line_amount", "sum"),
    )
    refunded = returns(transactions).groupby("customer_id")["line_amount"].sum().rename("refunds")
    rfm = purchased.join(refunded, how="left").fillna({"refunds": 0.0})
    rfm["monetary"] = (rfm["gross"] + rfm["refunds"]).round(4)
    rfm["recency_days"] = (pd.Timestamp(snapshot_date) - rfm["last_order_date"]).dt.days

    rfm["r_score"] = percentile_score(rfm["recency_days"], higher_is_better=False)
    rfm["f_score"] = percentile_score(rfm["frequency"])
    rfm["m_score"] = percentile_score(rfm["monetary"])
    rfm["rfm_score"] = (
        rfm["r_score"].astype(str) + rfm["f_score"].astype(str) + rfm["m_score"].astype(str)
    )
    rfm["segment"] = assign_segment(rfm["r_score"], rfm["f_score"])
    return rfm.reset_index()[RFM_COLUMNS].sort_values("customer_id").reset_index(drop=True)


def rfm_segment_summary(rfm: pd.DataFrame) -> pd.DataFrame:
    """Size, value and typical behaviour of each RFM segment."""
    if rfm.empty:
        return pd.DataFrame(
            columns=[
                "segment",
                "customers",
                "customer_share",
                "monetary",
                "monetary_share",
                "avg_recency_days",
                "avg_frequency",
                "avg_monetary",
            ]
        )
    summary = (
        rfm.groupby("segment", observed=True)
        .agg(
            customers=("customer_id", "size"),
            monetary=("monetary", "sum"),
            avg_recency_days=("recency_days", "mean"),
            avg_frequency=("frequency", "mean"),
            avg_monetary=("monetary", "mean"),
        )
        .reindex(SEGMENT_ORDER)
        .dropna(subset=["customers"])
        .reset_index()
    )
    summary["customers"] = summary["customers"].astype("int64")
    summary["customer_share"] = safe_divide(summary["customers"], summary["customers"].sum())
    summary["monetary_share"] = safe_divide(summary["monetary"], summary["monetary"].sum())
    return summary[
        [
            "segment",
            "customers",
            "customer_share",
            "monetary",
            "monetary_share",
            "avg_recency_days",
            "avg_frequency",
            "avg_monetary",
        ]
    ]


def new_vs_returning(transactions: pd.DataFrame) -> pd.DataFrame:
    """Monthly customers and revenue split into new, returning and unidentified buyers.

    A customer is new in the calendar month of their first observed order and returning in
    every later month. Orders without a customer ID are reported as unidentified.
    """
    order_table = orders(transactions)
    columns = ["period", "customer_type", "customers", "orders", "gross_revenue", "revenue_share"]
    if order_table.empty:
        return pd.DataFrame(columns=columns)

    order_table["period"] = month_start(order_table["order_date"])
    first_month = order_table.groupby("customer_id")["period"].transform("min")
    order_table["customer_type"] = np.where(
        order_table["customer_id"].isna(),
        "unidentified",
        np.where(order_table["period"] == first_month, "new", "returning"),
    )
    table = (
        order_table.groupby(["period", "customer_type"])
        .agg(
            customers=("customer_id", "nunique"),
            orders=("invoice_no", "size"),
            gross_revenue=("order_value", "sum"),
        )
        .reset_index()
    )
    table["revenue_share"] = safe_divide(
        table["gross_revenue"], table.groupby("period")["gross_revenue"].transform("sum")
    )
    return table[columns]


def repeat_purchase_rate(transactions: pd.DataFrame) -> float:
    """Share of identified customers with more than one sale invoice."""
    order_table = orders(transactions).dropna(subset=["customer_id"])
    if order_table.empty:
        return np.nan
    per_customer = order_table.groupby("customer_id")["invoice_no"].size()
    return float((per_customer > 1).mean())
