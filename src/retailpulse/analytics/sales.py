from __future__ import annotations

import numpy as np
import pandas as pd

from retailpulse.analytics.base import (
    month_start,
    orders,
    returns,
    round_amounts,
    safe_divide,
    sales,
)

TREND_COLUMNS = [
    "period",
    "orders",
    "gross_revenue",
    "return_value",
    "net_revenue",
    "average_order_value",
    "return_rate",
]


def kpi_summary(transactions: pd.DataFrame) -> dict[str, float]:
    """Headline KPIs. Revenue is in the source currency (GBP for the UCI dataset)."""
    sale_lines = sales(transactions)
    return_lines = returns(transactions)
    order_table = orders(transactions)

    gross_revenue = float(sale_lines["line_amount"].sum())
    return_value = float(-return_lines["line_amount"].sum())
    order_count = int(len(order_table))
    identified_revenue = float(
        sale_lines.loc[sale_lines["customer_id"].notna(), "line_amount"].sum()
    )
    return {
        "gross_revenue": gross_revenue,
        "return_value": return_value,
        "net_revenue": gross_revenue - return_value,
        "orders": order_count,
        "return_invoices": int(return_lines["invoice_no"].nunique()),
        "customers": int(sale_lines["customer_id"].nunique()),
        "units_sold": int(sale_lines["quantity"].sum()),
        "average_order_value": safe_divide(gross_revenue, order_count),
        "median_order_value": float(order_table["order_value"].median()) if order_count else np.nan,
        "return_rate": safe_divide(return_value, gross_revenue),
        "identified_revenue_share": safe_divide(identified_revenue, gross_revenue),
    }


def _period(dates: pd.Series, freq: str) -> pd.Series:
    if freq == "M":
        return month_start(dates)
    if freq == "D":
        return dates.dt.normalize()
    raise ValueError(f"Unsupported frequency '{freq}'. Use 'M' or 'D'.")


def revenue_trend(transactions: pd.DataFrame, freq: str = "M") -> pd.DataFrame:
    """Revenue, orders and returns per month ('M') or day ('D').

    The daily series contains every calendar day, with zeros on non-trading days, so the
    seven-day average always spans seven calendar days. Returns are attributed to the period
    in which the credit note was issued, because the source does not link a return to its
    original invoice.
    """
    sale_lines = sales(transactions)
    return_lines = returns(transactions)
    if sale_lines.empty and return_lines.empty:
        return pd.DataFrame(columns=TREND_COLUMNS)

    sold = sale_lines.groupby(_period(sale_lines["invoice_date"], freq)).agg(
        orders=("invoice_no", "nunique"), gross_revenue=("line_amount", "sum")
    )
    returned = (
        -return_lines.groupby(_period(return_lines["invoice_date"], freq))["line_amount"].sum()
    ).rename("return_value")

    trend = sold.join(returned, how="outer").sort_index()
    if freq == "D":
        trend = trend.reindex(pd.date_range(trend.index.min(), trend.index.max(), freq="D"))
    trend = trend.fillna(0.0)
    trend["orders"] = trend["orders"].astype("int64")
    trend["net_revenue"] = trend["gross_revenue"] - trend["return_value"]
    trend["average_order_value"] = safe_divide(trend["gross_revenue"], trend["orders"])
    trend["return_rate"] = safe_divide(trend["return_value"], trend["gross_revenue"])
    if freq == "M":
        trend["gross_revenue_growth"] = trend["gross_revenue"].pct_change()
    else:
        trend["gross_revenue_7d_avg"] = trend["gross_revenue"].rolling(7, min_periods=1).mean()
    return trend.rename_axis("period").reset_index()


def country_performance(transactions: pd.DataFrame) -> pd.DataFrame:
    """Orders, customers and revenue by the country recorded on the invoice."""
    sale_lines = sales(transactions)
    return_lines = returns(transactions)
    sold = sale_lines.groupby("country", observed=True).agg(
        orders=("invoice_no", "nunique"),
        customers=("customer_id", "nunique"),
        gross_revenue=("line_amount", "sum"),
    )
    returned = (-return_lines.groupby("country", observed=True)["line_amount"].sum()).rename(
        "return_value"
    )
    table = sold.join(returned, how="left").fillna({"return_value": 0.0})
    table[["gross_revenue", "return_value"]] = round_amounts(
        table[["gross_revenue", "return_value"]]
    )
    table["net_revenue"] = table["gross_revenue"] - table["return_value"]
    table["average_order_value"] = safe_divide(table["gross_revenue"], table["orders"])
    table["gross_revenue_share"] = safe_divide(table["gross_revenue"], table["gross_revenue"].sum())
    table["return_rate"] = safe_divide(table["return_value"], table["gross_revenue"])
    return (
        table.reset_index()
        .sort_values(["gross_revenue", "country"], ascending=[False, True])
        .reset_index(drop=True)
    )


def weekday_hour_pattern(transactions: pd.DataFrame) -> pd.DataFrame:
    """Gross revenue and orders by ISO weekday (1 = Monday) and hour of day."""
    sale_lines = sales(transactions)
    keys = [
        sale_lines["invoice_date"].dt.dayofweek.add(1).rename("iso_weekday"),
        sale_lines["invoice_date"].dt.hour.rename("hour"),
    ]
    return (
        sale_lines.groupby(keys)
        .agg(orders=("invoice_no", "nunique"), gross_revenue=("line_amount", "sum"))
        .reset_index()
    )
