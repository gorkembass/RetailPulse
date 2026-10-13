"""PostgreSQL integration tests.

They load the deterministic synthetic dataset into the database named by
RETAILPULSE_TEST_DATABASE_URL and check that the SQL analyses agree with the pandas
implementations. They are skipped when the variable is not set.
"""

from __future__ import annotations

import pandas as pd
import pytest

from retailpulse.analytics import cohorts, customers, products, sales
from retailpulse.cleaning import rules
from retailpulse.database.export import STAR_SCHEMA_EXPORTS, export_star_schema
from retailpulse.database.loader import table_counts
from retailpulse.database.queries import load_queries, run_analysis_files, run_query
from tests.conftest import SQL_DIR

pytestmark = pytest.mark.integration

ANALYSIS_DIR = SQL_DIR / "analysis"


def query(engine, file_name: str, name: str) -> pd.DataFrame:
    return run_query(engine, load_queries(ANALYSIS_DIR / file_name)[name])


def assert_tables_match(actual: pd.DataFrame, expected: pd.DataFrame, columns: list[str]) -> None:
    pd.testing.assert_frame_equal(
        actual[columns].reset_index(drop=True),
        expected[columns].reset_index(drop=True),
        check_dtype=False,
        check_exact=False,
        atol=1e-4,
    )


def test_staging_keeps_every_row_and_fact_keeps_only_valid_lines(warehouse, synthetic_transactions):
    counts = table_counts(warehouse)

    valid = (synthetic_transactions["line_type"] != rules.EXCLUDED).sum()
    assert counts["staging.transactions"] == len(synthetic_transactions)
    assert counts["analytics.fact_sales"] == valid


def test_warehouse_reconciles_with_staging(warehouse):
    result = query(warehouse, "06_data_quality.sql", "warehouse_reconciliation").iloc[0]

    assert result["fact_rows"] == result["expected_fact_rows"]
    assert result["fact_net_amount"] == pytest.approx(result["expected_net_amount"])
    assert result["fact_rows_without_product"] == 0


def test_sql_duplicate_detection_agrees_with_the_pipeline(warehouse, synthetic_transactions):
    result = query(warehouse, "06_data_quality.sql", "duplicate_recheck").iloc[0]

    assert result["disagreements"] == 0
    assert result["duplicates_found_in_sql"] == synthetic_transactions["is_duplicate"].sum()


def test_sql_exclusion_counts_match_the_pipeline(warehouse, synthetic_transactions):
    result = query(warehouse, "06_data_quality.sql", "exclusion_summary")

    expected = synthetic_transactions["exclusion_reason"].value_counts()
    actual = result.set_index("exclusion_reason")["line_count"]
    assert actual.to_dict() == expected.to_dict()


def test_headline_kpis_match_pandas(warehouse, synthetic_transactions):
    result = query(warehouse, "01_sales_overview.sql", "headline_kpis").iloc[0]

    expected = sales.kpi_summary(synthetic_transactions)
    for metric in ("gross_revenue", "return_value", "net_revenue", "median_order_value"):
        assert result[metric] == pytest.approx(expected[metric], abs=0.01)
    for metric in ("orders", "return_invoices", "customers", "units_sold"):
        assert result[metric] == expected[metric]
    assert result["average_order_value"] == pytest.approx(expected["average_order_value"], abs=0.01)
    assert result["return_rate"] == pytest.approx(expected["return_rate"], abs=1e-4)


def test_country_revenue_matches_pandas(warehouse, synthetic_transactions):
    result = query(warehouse, "01_sales_overview.sql", "revenue_by_country")

    expected = sales.country_performance(synthetic_transactions)
    assert_tables_match(
        result, expected, ["country", "orders", "customers", "gross_revenue", "return_value"]
    )


def test_monthly_trend_matches_pandas(warehouse, synthetic_transactions):
    result = query(warehouse, "05_revenue_trends.sql", "monthly_revenue_trend")
    result["period"] = pd.to_datetime(result["period"])

    expected = sales.revenue_trend(synthetic_transactions, "M")
    assert_tables_match(
        result, expected, ["period", "orders", "gross_revenue", "return_value", "net_revenue"]
    )


def test_daily_trend_matches_pandas(warehouse, synthetic_transactions):
    result = query(warehouse, "05_revenue_trends.sql", "daily_revenue_trend")
    result["period"] = pd.to_datetime(result["period"])

    expected = sales.revenue_trend(synthetic_transactions, "D")
    assert_tables_match(result, expected, ["period", "orders", "gross_revenue", "return_value"])
    assert result["gross_revenue_7d_avg"].to_numpy() == pytest.approx(
        expected["gross_revenue_7d_avg"].to_numpy(), abs=0.01
    )


def test_product_performance_matches_pandas(warehouse, synthetic_transactions, synthetic_products):
    result = query(warehouse, "02_product_performance.sql", "product_performance")

    expected = products.product_performance(synthetic_transactions, synthetic_products)
    assert_tables_match(
        result,
        expected,
        ["revenue_rank", "stock_code", "category", "units_sold", "gross_revenue", "return_value"],
    )


def test_product_returns_reconcile_with_headline_returns(warehouse):
    by_product = query(warehouse, "02_product_performance.sql", "product_performance")
    headline = query(warehouse, "01_sales_overview.sql", "headline_kpis").iloc[0]

    assert (by_product["gross_revenue"] == 0).any()
    assert by_product["return_value"].sum() == pytest.approx(headline["return_value"])
    assert by_product["gross_revenue"].sum() == pytest.approx(headline["gross_revenue"])


def test_category_performance_matches_pandas(warehouse, synthetic_transactions, synthetic_products):
    result = query(warehouse, "02_product_performance.sql", "category_performance")

    expected = products.category_performance(synthetic_transactions, synthetic_products)
    assert_tables_match(
        result, expected, ["category", "products", "gross_revenue", "return_value", "net_revenue"]
    )


def test_rfm_scores_match_pandas(warehouse, synthetic_transactions):
    result = query(warehouse, "03_customer_segmentation.sql", "rfm_scores")

    expected = customers.rfm_scores(synthetic_transactions)
    assert len(result) == len(expected) > 0
    assert_tables_match(
        result,
        expected,
        [
            "customer_id",
            "recency_days",
            "frequency",
            "monetary",
            "r_score",
            "f_score",
            "m_score",
            "rfm_score",
            "segment",
        ],
    )


def test_new_vs_returning_matches_pandas(warehouse, synthetic_transactions):
    result = query(warehouse, "03_customer_segmentation.sql", "new_vs_returning_by_month")
    result["period"] = pd.to_datetime(result["period"])

    expected = customers.new_vs_returning(synthetic_transactions)
    assert_tables_match(
        result, expected, ["period", "customer_type", "customers", "orders", "gross_revenue"]
    )


def test_cohort_retention_matches_pandas(warehouse, synthetic_transactions):
    result = query(warehouse, "04_cohort_retention.sql", "cohort_retention")
    result["cohort_month"] = pd.to_datetime(result["cohort_month"])

    expected = cohorts.cohort_retention(synthetic_transactions)
    assert_tables_match(
        result,
        expected,
        ["cohort_month", "period_index", "cohort_size", "active_customers", "gross_revenue"],
    )
    assert result["retention_rate"].to_numpy() == pytest.approx(
        expected["retention_rate"].to_numpy(), abs=1e-4
    )


def test_average_retention_matches_pandas(warehouse, synthetic_transactions):
    result = query(warehouse, "04_cohort_retention.sql", "average_retention_by_period")

    expected = cohorts.average_retention(cohorts.cohort_retention(synthetic_transactions))
    assert_tables_match(result, expected, ["period_index", "cohorts"])
    assert result["retention_rate"].to_numpy() == pytest.approx(
        expected["retention_rate"].to_numpy(), abs=1e-4
    )


def test_fact_table_rejects_rows_that_violate_business_rules(warehouse):
    statement = """
        INSERT INTO analytics.fact_sales
        SELECT 999999999, invoice_no, invoice_date, date_key, stock_code, customer_id, country,
               'sale', -1, unit_price, line_amount
        FROM analytics.fact_sales
        LIMIT 1
    """

    with pytest.raises(Exception, match="amount_sign_matches_line_type"):
        run_query(warehouse, statement)


def test_every_analysis_query_runs_and_is_exported(warehouse, tmp_path):
    written = run_analysis_files(warehouse, ANALYSIS_DIR, tmp_path)

    expected = sum(len(load_queries(path)) for path in ANALYSIS_DIR.glob("*.sql"))
    assert len(written) == expected
    assert all(path.stat().st_size > 0 for path in written)


def test_star_schema_export_matches_table_row_counts(warehouse, tmp_path):
    written = export_star_schema(warehouse, tmp_path)

    assert {path.stem for path in written} == set(STAR_SCHEMA_EXPORTS)
    fact = pd.read_csv(tmp_path / "fact_sales.csv")
    assert len(fact) == table_counts(warehouse)["analytics.fact_sales"]
    assert set(fact["line_type"]) == {"sale", "return"}
