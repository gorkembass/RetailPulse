from __future__ import annotations

import pandas as pd

from retailpulse.analytics.base import returns, round_amounts, safe_divide, sales


def product_performance(transactions: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Revenue, units and returns per product, ranked by gross revenue with a Pareto share.

    Products that were only returned in the period are kept with zero sales, so that product
    and category totals reconcile with the headline return value.
    """
    sale_lines = sales(transactions)
    return_lines = returns(transactions)
    sold = sale_lines.groupby("stock_code", observed=True).agg(
        orders=("invoice_no", "nunique"),
        units_sold=("quantity", "sum"),
        gross_revenue=("line_amount", "sum"),
    )
    returned = return_lines.groupby("stock_code", observed=True).agg(
        units_returned=("quantity", lambda quantity: -quantity.sum()),
        return_value=("line_amount", lambda amount: -amount.sum()),
    )
    table = sold.join(returned, how="outer").fillna(0)
    count_columns = ["orders", "units_sold", "units_returned"]
    table[count_columns] = table[count_columns].astype("int64")
    table[["gross_revenue", "return_value"]] = round_amounts(
        table[["gross_revenue", "return_value"]]
    )
    table["net_revenue"] = table["gross_revenue"] - table["return_value"]
    table["return_rate"] = safe_divide(table["return_value"], table["gross_revenue"])
    table = (
        table.reset_index()
        .merge(products, on="stock_code", how="left")
        .sort_values(["gross_revenue", "stock_code"], ascending=[False, True])
        .reset_index(drop=True)
    )
    table["revenue_rank"] = table.index + 1
    table["cumulative_revenue_share"] = safe_divide(
        table["gross_revenue"].cumsum(), table["gross_revenue"].sum()
    )
    return table[
        [
            "revenue_rank",
            "stock_code",
            "description",
            "category",
            "orders",
            "units_sold",
            "gross_revenue",
            "units_returned",
            "return_value",
            "net_revenue",
            "return_rate",
            "cumulative_revenue_share",
        ]
    ]


def category_performance(transactions: pd.DataFrame, products: pd.DataFrame) -> pd.DataFrame:
    """Revenue, breadth and returns per derived product category."""
    by_product = product_performance(transactions, products)
    table = (
        by_product.groupby("category", observed=True)
        .agg(
            products=("units_sold", lambda units: int((units > 0).sum())),
            units_sold=("units_sold", "sum"),
            gross_revenue=("gross_revenue", "sum"),
            return_value=("return_value", "sum"),
            net_revenue=("net_revenue", "sum"),
        )
        .reset_index()
    )
    table["gross_revenue_share"] = safe_divide(table["gross_revenue"], table["gross_revenue"].sum())
    table["return_rate"] = safe_divide(table["return_value"], table["gross_revenue"])
    table["revenue_per_product"] = safe_divide(table["gross_revenue"], table["products"])
    return table.sort_values(["gross_revenue", "category"], ascending=[False, True]).reset_index(
        drop=True
    )
