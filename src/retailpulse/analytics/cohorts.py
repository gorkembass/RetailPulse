from __future__ import annotations

import pandas as pd

from retailpulse.analytics.base import month_start, safe_divide, sales

COHORT_COLUMNS = [
    "cohort_month",
    "period_index",
    "cohort_size",
    "active_customers",
    "retention_rate",
    "gross_revenue",
]


def cohort_retention(transactions: pd.DataFrame) -> pd.DataFrame:
    """Monthly acquisition cohorts with the customers active in each later month.

    ``period_index`` is the number of calendar months since the first purchase, so index 0
    is the acquisition month and always has a retention rate of 1. Every period a cohort
    could have been observed in is present, with zero activity where nobody purchased;
    periods after the last month of data are absent because they are unknown, not zero.
    """
    all_sales = sales(transactions)
    sale_lines = all_sales.dropna(subset=["customer_id"])
    if sale_lines.empty:
        return pd.DataFrame(columns=COHORT_COLUMNS)

    activity = sale_lines[["customer_id", "line_amount"]].copy()
    activity["activity_month"] = month_start(sale_lines["invoice_date"])
    activity["cohort_month"] = activity.groupby("customer_id")["activity_month"].transform("min")
    activity["period_index"] = _months_between(activity["cohort_month"], activity["activity_month"])
    observed = (
        activity.groupby(["cohort_month", "period_index"])
        .agg(active_customers=("customer_id", "nunique"), gross_revenue=("line_amount", "sum"))
        .reset_index()
    )
    sizes = observed.loc[
        observed["period_index"] == 0, ["cohort_month", "active_customers"]
    ].rename(columns={"active_customers": "cohort_size"})

    last_month = month_start(all_sales["invoice_date"]).max()
    sizes["periods_observed"] = _months_between(
        sizes["cohort_month"], pd.Series(last_month, index=sizes.index)
    )
    grid = sizes.loc[sizes.index.repeat(sizes["periods_observed"] + 1)].copy()
    grid["period_index"] = grid.groupby("cohort_month").cumcount()

    cohorts = grid.merge(observed, on=["cohort_month", "period_index"], how="left").fillna(
        {"active_customers": 0, "gross_revenue": 0.0}
    )
    cohorts["active_customers"] = cohorts["active_customers"].astype("int64")
    cohorts["retention_rate"] = safe_divide(cohorts["active_customers"], cohorts["cohort_size"])
    return (
        cohorts[COHORT_COLUMNS].sort_values(["cohort_month", "period_index"]).reset_index(drop=True)
    )


def _months_between(start: pd.Series, end: pd.Series) -> pd.Series:
    return (end.dt.year - start.dt.year) * 12 + end.dt.month - start.dt.month


def retention_matrix(cohorts: pd.DataFrame) -> pd.DataFrame:
    """Pivot cohort retention to a cohort-by-period matrix of retention rates."""
    if cohorts.empty:
        return pd.DataFrame()
    return cohorts.pivot(index="cohort_month", columns="period_index", values="retention_rate")


def average_retention(cohorts: pd.DataFrame) -> pd.DataFrame:
    """Customer-weighted retention per period across all cohorts observed at that period."""
    if cohorts.empty:
        return pd.DataFrame(columns=["period_index", "cohorts", "retention_rate"])
    table = (
        cohorts.groupby("period_index")
        .agg(
            cohorts=("cohort_month", "nunique"),
            active_customers=("active_customers", "sum"),
            cohort_size=("cohort_size", "sum"),
        )
        .reset_index()
    )
    table["retention_rate"] = safe_divide(table["active_customers"], table["cohort_size"])
    return table[["period_index", "cohorts", "retention_rate"]]
