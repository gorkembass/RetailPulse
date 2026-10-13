from __future__ import annotations

import pandas as pd
import streamlit as st

from retailpulse.analytics import profitability, sales

import charts
from views.components import CURRENCY, chart_card, metric_row, money, percent


def render(transactions: pd.DataFrame) -> None:
    st.title("Sales overview")
    kpis = sales.kpi_summary(transactions)
    if kpis["orders"] == 0:
        st.info("No sales match the current filters.")
        return

    metric_row(
        [
            ("Gross revenue", money(kpis["gross_revenue"]), "Value of all valid sale lines."),
            ("Net revenue", money(kpis["net_revenue"]), "Gross revenue minus returned value."),
            ("Orders", f"{kpis['orders']:,}", "Invoices with at least one valid sale line."),
            (
                "Average order value",
                money(kpis["average_order_value"], decimals=0),
                f"Median order value is {money(kpis['median_order_value'], decimals=0)}; "
                "a few very large wholesale orders pull the mean up.",
            ),
            (
                "Return rate",
                percent(kpis["return_rate"]),
                "Returned value as a share of gross revenue.",
            ),
        ]
    )

    monthly = sales.revenue_trend(transactions, "M")
    daily = sales.revenue_trend(transactions, "D")
    left, right = st.columns(2)
    with left:
        chart_card(
            "Gross revenue by month",
            charts.columns(
                monthly, "period", "gross_revenue", value_format=",.0f", value_prefix=CURRENCY
            ),
            monthly[["period", "orders", "gross_revenue", "return_value", "net_revenue"]],
            note="The last month in the source is partial (it ends on 9 Dec 2011).",
        )
    with right:
        chart_card(
            "Return rate by month",
            charts.columns(monthly, "period", "return_rate", value_format=".1%"),
            monthly[["period", "gross_revenue", "return_value", "return_rate"]],
            note="Dated by credit note. Spikes are single large orders cancelled in full.",
        )

    chart_card(
        "Gross revenue per day, 7-day average",
        charts.line(
            daily, "period", "gross_revenue_7d_avg", value_format=",.0f", value_prefix=CURRENCY
        ),
        daily[["period", "orders", "gross_revenue", "gross_revenue_7d_avg"]],
    )

    countries = sales.country_performance(transactions)
    left, right = st.columns(2)
    with left:
        home = countries[countries["country"] == "United Kingdom"]
        home_share = home["gross_revenue_share"].iloc[0] if not home.empty else 0.0
        international = countries[countries["country"] != "United Kingdom"].head(10)
        if international.empty:
            st.subheader("International revenue by country")
            st.caption("No international sales match the current filters.")
        else:
            chart_card(
                "International gross revenue, top 10 countries",
                charts.bars(
                    international,
                    "country",
                    "gross_revenue",
                    value_format=",.0f",
                    value_prefix=CURRENCY,
                ),
                countries,
                note=f"The United Kingdom is excluded from the chart; it accounts for "
                f"{percent(home_share)} of gross revenue in this selection.",
            )
    with right:
        st.subheader("Revenue is not profit")
        st.caption(
            "The source has no cost data, so profit cannot be measured. The table shows what "
            "gross margin would be under three assumed cost-of-goods ratios. It is a "
            "scenario, not a result."
        )
        scenarios = profitability.margin_scenarios(kpis["gross_revenue"], kpis["return_value"])
        st.dataframe(
            scenarios[
                ["assumed_cogs_ratio", "net_revenue", "assumed_cogs", "assumed_gross_margin"]
            ],
            hide_index=True,
            column_config={
                "assumed_cogs_ratio": st.column_config.NumberColumn(
                    "Assumed COGS ratio", format="percent"
                ),
                "net_revenue": st.column_config.NumberColumn(
                    "Net revenue", format=f"{CURRENCY}%,.0f"
                ),
                "assumed_cogs": st.column_config.NumberColumn(
                    "Assumed COGS", format=f"{CURRENCY}%,.0f"
                ),
                "assumed_gross_margin": st.column_config.NumberColumn(
                    "Assumed gross margin", format=f"{CURRENCY}%,.0f"
                ),
            },
        )
