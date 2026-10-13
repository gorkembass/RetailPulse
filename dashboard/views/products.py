from __future__ import annotations

import pandas as pd
import streamlit as st

from retailpulse.analytics import products as product_analytics

import charts
from views.components import CURRENCY, chart_card, metric_row, money, percent

MIN_REVENUE_FOR_RETURN_RANKING = 1000


def render(transactions: pd.DataFrame, product_table: pd.DataFrame) -> None:
    st.title("Products")
    by_product = product_analytics.product_performance(transactions, product_table)
    sold = by_product[by_product["gross_revenue"] > 0]
    if sold.empty:
        st.info("No sales match the current filters.")
        return
    by_category = product_analytics.category_performance(transactions, product_table)

    top_decile = sold.head(max(1, len(sold) // 10))
    products_for_80 = int((sold["cumulative_revenue_share"] < 0.8).sum()) + 1
    metric_row(
        [
            ("Products sold", f"{len(sold):,}", "Distinct stock codes with at least one sale."),
            (
                "Top 10% revenue share",
                percent(top_decile["gross_revenue"].sum() / sold["gross_revenue"].sum()),
                f"Share of gross revenue from the {len(top_decile):,} best-selling products.",
            ),
            (
                "Products for 80%",
                f"{products_for_80:,}",
                f"Number of top products that make up 80% of gross revenue "
                f"({percent(products_for_80 / len(sold))} of the products sold).",
            ),
            (
                "Largest category",
                by_category.iloc[0]["category"],
                f"{percent(by_category.iloc[0]['gross_revenue_share'])} of gross revenue.",
            ),
        ]
    )

    st.caption(
        "Categories are derived from keywords in product descriptions because the source has "
        "no category field. Treat them as an approximate grouping."
    )
    left, right = st.columns(2)
    with left:
        chart_card(
            "Gross revenue by category",
            charts.bars(
                by_category, "category", "gross_revenue", value_format=",.0f", value_prefix=CURRENCY
            ),
            by_category,
            note="Value of valid sale lines, before returns.",
        )
    with right:
        chart_card(
            "Return rate by category",
            charts.bars(
                by_category.sort_values("return_rate", ascending=False),
                "category",
                "return_rate",
                value_format=".1%",
            ),
            by_category[["category", "gross_revenue", "return_value", "return_rate"]],
            note="Returned value as a share of the category's gross revenue.",
        )

    top_products = sold.sort_values("net_revenue", ascending=False).head(15)
    chart_card(
        "Top 15 products by net revenue",
        charts.bars(
            top_products, "description", "net_revenue", value_format=",.0f", value_prefix=CURRENCY
        ),
        top_products,
        note="Ranked on net revenue so that orders cancelled in full do not inflate the list.",
    )

    st.subheader("Products with the highest return rate")
    st.caption(
        f"Limited to products with at least {money(MIN_REVENUE_FOR_RETURN_RANKING)} of gross "
        "revenue, so that small denominators do not dominate."
    )
    most_returned = (
        sold[sold["gross_revenue"] >= MIN_REVENUE_FOR_RETURN_RANKING]
        .sort_values("return_rate", ascending=False)
        .head(10)
    )
    st.dataframe(
        most_returned[
            [
                "stock_code",
                "description",
                "category",
                "gross_revenue",
                "return_value",
                "return_rate",
            ]
        ],
        hide_index=True,
        width="stretch",
        column_config={
            "stock_code": "Stock code",
            "description": "Product",
            "category": "Category",
            "gross_revenue": st.column_config.NumberColumn(
                "Gross revenue", format=f"{CURRENCY}%,.0f"
            ),
            "return_value": st.column_config.NumberColumn(
                "Returned value", format=f"{CURRENCY}%,.0f"
            ),
            "return_rate": st.column_config.NumberColumn("Return rate", format="percent"),
        },
    )
