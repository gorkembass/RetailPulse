from __future__ import annotations

import pandas as pd

from retailpulse.cleaning.rules import DUPLICATE, EXCLUDED, EXCLUSION_REASONS, RETURN, SALE


def line_type_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """Row count and signed value of every line type."""
    summary = (
        transactions.groupby("line_type", observed=True)
        .agg(rows=("source_row", "size"), line_amount=("line_amount", "sum"))
        .reindex([SALE, RETURN, EXCLUDED], fill_value=0)
        .reset_index()
    )
    total = len(transactions)
    summary["row_share"] = summary["rows"] / total if total else 0.0
    return summary


def exclusion_summary(transactions: pd.DataFrame) -> pd.DataFrame:
    """Rows and signed value removed by each exclusion rule, in rule precedence order."""
    excluded = transactions[transactions["line_type"] == EXCLUDED]
    summary = (
        excluded.groupby("exclusion_reason", observed=True)
        .agg(
            rows=("source_row", "size"),
            line_amount=("line_amount", "sum"),
            rows_without_customer=("has_customer_id", lambda flags: int((~flags).sum())),
        )
        .reindex(list(EXCLUSION_REASONS), fill_value=0)
        .rename_axis("exclusion_reason")
        .reset_index()
    )
    total = len(transactions)
    summary["row_share"] = summary["rows"] / total if total else 0.0
    return summary


def customer_coverage(transactions: pd.DataFrame) -> pd.DataFrame:
    """Share of sale lines, orders and revenue that carry a customer identifier."""
    sales = transactions[transactions["line_type"] == SALE]
    grouped = sales.groupby("has_customer_id", observed=True).agg(
        rows=("source_row", "size"),
        orders=("invoice_no", "nunique"),
        gross_revenue=("line_amount", "sum"),
    )
    coverage = grouped.reindex([True, False], fill_value=0).reset_index()
    for column in ("rows", "orders", "gross_revenue"):
        total = coverage[column].sum()
        coverage[f"{column}_share"] = coverage[column] / total if total else 0.0
    return coverage


def duplicate_sensitivity(transactions: pd.DataFrame) -> pd.DataFrame:
    """Gross revenue with and without the lines excluded as duplicates."""
    sales = transactions[transactions["line_type"] == SALE]["line_amount"].sum()
    duplicates = transactions[
        (transactions["exclusion_reason"] == DUPLICATE) & ~transactions["is_cancellation"]
    ]["line_amount"].sum()
    return pd.DataFrame(
        {
            "scenario": ["duplicates_excluded", "duplicates_kept"],
            "gross_revenue": [sales, sales + duplicates],
        }
    ).assign(difference_vs_base=lambda frame: frame["gross_revenue"] - sales)


def build_quality_report(transactions: pd.DataFrame) -> dict[str, pd.DataFrame]:
    return {
        "line_type_summary": line_type_summary(transactions),
        "exclusion_summary": exclusion_summary(transactions),
        "customer_coverage": customer_coverage(transactions),
        "duplicate_sensitivity": duplicate_sensitivity(transactions),
    }
