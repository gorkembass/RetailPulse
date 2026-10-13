from __future__ import annotations

import pandas as pd
import streamlit as st

from retailpulse.analytics import cohorts, customers, sales

import charts
from views.components import CURRENCY, chart_card, metric_row, percent

CUSTOMER_TYPES = {
    "new": "New customers",
    "returning": "Returning customers",
    "unidentified": "No customer ID",
}


def render(transactions: pd.DataFrame) -> None:
    st.title("Customers")
    rfm = customers.rfm_scores(transactions)
    if rfm.empty:
        st.info("No orders with a customer ID match the current filters.")
        return
    kpis = sales.kpi_summary(transactions)

    metric_row(
        [
            ("Identified customers", f"{len(rfm):,}", "Customers with at least one valid sale."),
            (
                "Repeat purchase rate",
                percent(customers.repeat_purchase_rate(transactions)),
                "Share of identified customers with more than one order in the selection.",
            ),
            (
                "Orders per customer",
                f"{rfm['frequency'].mean():.1f}",
                f"Median is {rfm['frequency'].median():.0f}.",
            ),
            (
                "Revenue with a customer ID",
                percent(kpis["identified_revenue_share"]),
                "Customer analyses cover only this share of gross revenue.",
            ),
        ]
    )

    segments = customers.rfm_segment_summary(rfm).sort_values("monetary_share", ascending=False)
    st.subheader("RFM segments")
    st.caption(
        "Segments combine recency and frequency scores (1 to 5). Monetary value is net of "
        "returns. Both charts list segments in the same order."
    )
    left, right = st.columns(2)
    with left:
        chart_card(
            "Share of customers",
            charts.bars(segments, "segment", "customer_share", value_format=".1%"),
            segments,
        )
    with right:
        chart_card(
            "Share of net revenue",
            charts.bars(segments, "segment", "monetary_share", value_format=".1%"),
            segments[["segment", "customers", "monetary", "monetary_share", "avg_monetary"]],
        )

    mix = customers.new_vs_returning(transactions)
    chart_card(
        "Gross revenue by customer type",
        charts.stacked_columns(
            mix,
            "period",
            "gross_revenue",
            "customer_type",
            CUSTOMER_TYPES,
            value_format=",.0f",
            value_prefix=CURRENCY,
        ),
        mix,
        note="A customer is new in the month of their first observed order. Customers who "
        "bought before the data starts are counted as new when they first appear.",
    )

    cohort_table = cohorts.cohort_retention(transactions)
    matrix = (
        cohorts.retention_matrix(cohort_table).drop(columns=0, errors="ignore").dropna(how="all")
    )
    if matrix.empty:
        return
    chart_card(
        "Monthly cohort retention",
        charts.retention_heatmap(matrix, height=90 + 30 * len(matrix)),
        cohort_table,
        note="Share of each first-purchase cohort that ordered again N months later. Blank "
        "cells are months that had not happened yet. The final month is partial.",
    )
