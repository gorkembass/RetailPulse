from __future__ import annotations

import pandas as pd
import streamlit as st

from retailpulse.analytics.base import month_start
from retailpulse.cleaning import rules
from retailpulse.cleaning.quality import build_quality_report

import charts
from views.components import CURRENCY, chart_card, metric_row, percent

RULE_DESCRIPTIONS = {
    rules.INVALID_FIELD: "Invoice, stock code, quantity or price is missing or not a valid value.",
    rules.INVALID_DATE: "Invoice date is missing, unparseable or outside the plausible range.",
    rules.INVALID_INVOICE: "Invoice number is not six digits with an optional C prefix.",
    rules.NON_PRODUCT: "Postage, fees, manual adjustments and other non-merchandise codes.",
    rules.INCONSISTENT_CANCELLATION: "Cancellation invoice with a non-negative quantity.",
    rules.NON_POSITIVE_QUANTITY: "Zero or negative quantity outside a cancellation "
    "(stock write-offs).",
    rules.NON_POSITIVE_PRICE: "Unit price of zero or less (free items and corrections).",
    rules.DUPLICATE: "Exact repeat of an earlier line; the first occurrence is kept.",
}


def render(transactions: pd.DataFrame) -> None:
    st.title("Data quality")
    if transactions.empty:
        st.info("No rows match the current filters.")
        return
    st.caption(
        "Every source row is kept and classified. Excluded rows stay in the staging layer "
        "with the rule that excluded them, so each figure below can be audited."
    )
    report = build_quality_report(transactions)
    line_types = report["line_type_summary"].set_index("line_type")
    coverage = report["customer_coverage"].set_index("has_customer_id")

    metric_row(
        [
            ("Source rows", f"{len(transactions):,}", "Rows in the selection, before any rule."),
            (
                "Sale lines",
                f"{line_types.loc[rules.SALE, 'rows']:,}",
                f"{percent(line_types.loc[rules.SALE, 'row_share'])} of source rows.",
            ),
            (
                "Return lines",
                f"{line_types.loc[rules.RETURN, 'rows']:,}",
                f"{percent(line_types.loc[rules.RETURN, 'row_share'])} of source rows.",
            ),
            (
                "Excluded lines",
                f"{line_types.loc[rules.EXCLUDED, 'rows']:,}",
                f"{percent(line_types.loc[rules.EXCLUDED, 'row_share'])} of source rows.",
            ),
            (
                "Unidentified revenue",
                percent(coverage.loc[False, "gross_revenue_share"]),
                "Share of gross revenue with no customer ID. It is counted in revenue but "
                "invisible to RFM, cohort and repeat-purchase analysis.",
            ),
        ]
    )

    st.subheader("Excluded rows by rule")
    st.caption("Rules are applied in this order; a row is reported under the first rule it breaks.")
    exclusions = report["exclusion_summary"].copy()
    exclusions.insert(
        1, "rule", exclusions["exclusion_reason"].map(RULE_DESCRIPTIONS).fillna("Undocumented rule")
    )
    st.dataframe(
        exclusions[["exclusion_reason", "rule", "rows", "row_share", "line_amount"]],
        hide_index=True,
        width="stretch",
        column_config={
            "exclusion_reason": "Reason code",
            "rule": st.column_config.TextColumn("Rule", width="large"),
            "rows": st.column_config.NumberColumn("Rows", format="localized"),
            "row_share": st.column_config.NumberColumn("Share of rows", format="percent"),
            "line_amount": st.column_config.NumberColumn(
                "Signed value excluded", format=f"{CURRENCY}%,.0f"
            ),
        },
    )

    sale_lines = transactions[transactions["line_type"] == rules.SALE]
    if sale_lines.empty:
        return
    monthly = (
        sale_lines.assign(period=month_start(sale_lines["invoice_date"]))
        .groupby("period")
        .apply(
            lambda month: pd.Series(
                {
                    "gross_revenue": month["line_amount"].sum(),
                    "revenue_without_customer": month.loc[
                        ~month["has_customer_id"], "line_amount"
                    ].sum(),
                }
            ),
            include_groups=False,
        )
        .reset_index()
    )
    monthly["share_without_customer"] = (
        monthly["revenue_without_customer"] / monthly["gross_revenue"]
    )
    left, right = st.columns(2)
    with left:
        chart_card(
            "Share of gross revenue without a customer ID",
            charts.columns(monthly, "period", "share_without_customer", value_format=".1%"),
            monthly,
            note="Months with a high share understate customer-level metrics the most.",
        )
    with right:
        st.subheader("Sensitivity to the duplicate rule")
        st.caption(
            "Exact duplicate lines may be genuine repeat scans or export errors; the source "
            "cannot tell them apart. This is the revenue at stake in that decision."
        )
        sensitivity = report["duplicate_sensitivity"]
        st.dataframe(
            sensitivity,
            hide_index=True,
            width="stretch",
            column_config={
                "scenario": "Scenario",
                "gross_revenue": st.column_config.NumberColumn(
                    "Gross revenue", format=f"{CURRENCY}%,.0f"
                ),
                "difference_vs_base": st.column_config.NumberColumn(
                    "Difference vs base", format=f"{CURRENCY}%,.0f"
                ),
            },
        )
