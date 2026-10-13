from __future__ import annotations

import json
import logging
from pathlib import Path

import pandas as pd

from retailpulse.analytics import cohorts, customers, products, profitability, sales
from retailpulse.cleaning.products import build_products
from retailpulse.cleaning.quality import build_quality_report
from retailpulse.cleaning.rules import classify_transactions
from retailpulse.config import Paths
from retailpulse.database.connection import get_engine
from retailpulse.database.export import export_star_schema
from retailpulse.database.loader import load_warehouse
from retailpulse.database.queries import run_analysis_files
from retailpulse.ingestion.download import acquire, read_metadata
from retailpulse.ingestion.reader import read_raw

logger = logging.getLogger(__name__)


def ingest(paths: Paths, source: str = "auto", force: bool = False) -> Path:
    return acquire(paths.raw, paths.source_metadata, source=source, force=force)


def clean(paths: Paths) -> pd.DataFrame:
    metadata = read_metadata(paths.source_metadata)
    raw = read_raw(paths.raw / metadata["file"])
    transactions = classify_transactions(raw)
    product_table = build_products(transactions)

    paths.processed.mkdir(parents=True, exist_ok=True)
    transactions.to_parquet(paths.transactions, index=False)
    product_table.to_parquet(paths.products, index=False)

    paths.quality_reports.mkdir(parents=True, exist_ok=True)
    for name, report in build_quality_report(transactions).items():
        report.to_csv(paths.quality_reports / f"{name}.csv", index=False)

    counts = transactions["line_type"].value_counts().to_dict()
    logger.info("Classified %d rows: %s", len(transactions), counts)
    return transactions


def read_processed(paths: Paths) -> tuple[pd.DataFrame, pd.DataFrame]:
    if not paths.transactions.exists():
        raise FileNotFoundError(
            f"{paths.transactions} not found. Run 'retailpulse clean' before this step."
        )
    return pd.read_parquet(paths.transactions), pd.read_parquet(paths.products)


def load(paths: Paths) -> dict[str, int]:
    transactions, product_table = read_processed(paths)
    return load_warehouse(get_engine(), transactions, product_table, paths.sql / "schema")


def run_sql(paths: Paths) -> list[Path]:
    return run_analysis_files(get_engine(), paths.sql / "analysis", paths.sql_results)


def build_analytics(
    transactions: pd.DataFrame, product_table: pd.DataFrame
) -> dict[str, pd.DataFrame]:
    """Compute every analytical table in pandas from the classified transactions."""
    kpis = sales.kpi_summary(transactions)
    rfm = customers.rfm_scores(transactions)
    cohort_table = cohorts.cohort_retention(transactions)
    return {
        "kpi_summary": pd.DataFrame({"metric": list(kpis), "value": list(kpis.values())}),
        "monthly_revenue": sales.revenue_trend(transactions, "M"),
        "daily_revenue": sales.revenue_trend(transactions, "D"),
        "country_performance": sales.country_performance(transactions),
        "product_performance": products.product_performance(transactions, product_table),
        "category_performance": products.category_performance(transactions, product_table),
        "new_vs_returning": customers.new_vs_returning(transactions),
        "rfm_customers": rfm,
        "rfm_segments": customers.rfm_segment_summary(rfm),
        "cohort_retention": cohort_table,
        "average_retention": cohorts.average_retention(cohort_table),
        "margin_scenarios": profitability.margin_scenarios(
            kpis["gross_revenue"], kpis["return_value"]
        ),
    }


def analyze(paths: Paths) -> list[Path]:
    transactions, product_table = read_processed(paths)
    metadata = read_metadata(paths.source_metadata)
    paths.analytics.mkdir(parents=True, exist_ok=True)

    written = []
    for name, table in build_analytics(transactions, product_table).items():
        target = paths.analytics / f"{name}.csv"
        table.to_csv(target, index=False)
        written.append(target)

    run_info = {
        "source": metadata["source"],
        "is_synthetic": metadata["is_synthetic"],
        "source_sha256": metadata["sha256"],
        "rows": len(transactions),
        "first_invoice_date": str(transactions["invoice_date"].min()),
        "last_invoice_date": str(transactions["invoice_date"].max()),
    }
    (paths.analytics / "run_metadata.json").write_text(
        json.dumps(run_info, indent=2) + "\n", encoding="utf-8"
    )
    logger.info("Wrote %d analytical tables to %s", len(written), paths.analytics)
    return written


def export(paths: Paths) -> list[Path]:
    return export_star_schema(get_engine(), paths.dashboard_exports)


def run_all(paths: Paths, source: str = "auto") -> None:
    if paths.source_metadata.exists():
        logger.info("Raw data already present; skipping ingestion")
    else:
        ingest(paths, source=source)
    clean(paths)
    load(paths)
    run_sql(paths)
    analyze(paths)
    export(paths)
