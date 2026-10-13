from __future__ import annotations

import pandas as pd
import pytest

from retailpulse.cleaning import rules
from retailpulse.database.queries import parse_queries
from retailpulse.ingestion import download
from retailpulse.ingestion.reader import read_raw
from retailpulse.ingestion.synthetic import RAW_COLUMNS, generate_synthetic_transactions
from tests.conftest import SQL_DIR


def test_synthetic_data_is_deterministic():
    first = generate_synthetic_transactions(seed=7)
    second = generate_synthetic_transactions(seed=7)

    pd.testing.assert_frame_equal(first, second)
    assert list(first.columns) == RAW_COLUMNS


def test_synthetic_data_changes_with_the_seed():
    assert not generate_synthetic_transactions(seed=1).equals(
        generate_synthetic_transactions(seed=2)
    )


def test_synthetic_data_exercises_every_major_rule(synthetic_transactions):
    reasons = set(synthetic_transactions["exclusion_reason"].dropna())

    assert {rules.SALE, rules.RETURN, rules.EXCLUDED} == set(synthetic_transactions["line_type"])
    assert {
        rules.DUPLICATE,
        rules.NON_PRODUCT,
        rules.NON_POSITIVE_PRICE,
        rules.NON_POSITIVE_QUANTITY,
    } <= reasons
    assert not synthetic_transactions["has_customer_id"].all()


def test_synthetic_source_is_labelled_in_metadata(tmp_path):
    metadata_path = tmp_path / "source_metadata.json"

    target = download.acquire(tmp_path, metadata_path, source="synthetic")

    metadata = download.read_metadata(metadata_path)
    assert metadata["is_synthetic"] is True
    assert metadata["source"] == "synthetic"
    assert metadata["sha256"] == download.sha256_of(target)
    assert len(read_raw(target)) == metadata["rows"]


def test_existing_raw_file_is_never_overwritten_implicitly(tmp_path):
    metadata_path = tmp_path / "source_metadata.json"
    target = download.acquire(tmp_path, metadata_path, source="synthetic")
    original = target.read_bytes()

    with pytest.raises(download.RawDataExistsError):
        download.acquire(tmp_path, metadata_path, source="synthetic")

    assert target.read_bytes() == original


def test_failed_download_falls_back_to_labelled_synthetic_data(tmp_path, monkeypatch):
    def unreachable(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(download.urllib.request, "urlopen", unreachable)
    metadata_path = tmp_path / "source_metadata.json"

    target = download.acquire(tmp_path, metadata_path, source="auto")

    assert target.name == download.SYNTHETIC_FILENAME
    assert download.read_metadata(metadata_path)["is_synthetic"] is True


def test_explicit_uci_source_does_not_fall_back(tmp_path, monkeypatch):
    def unreachable(*args, **kwargs):
        raise OSError("network unreachable")

    monkeypatch.setattr(download.urllib.request, "urlopen", unreachable)

    with pytest.raises(OSError, match="network unreachable"):
        download.acquire(tmp_path, tmp_path / "source_metadata.json", source="uci")

    assert not (tmp_path / "source_metadata.json").exists()


def test_missing_metadata_explains_the_required_step(tmp_path):
    with pytest.raises(FileNotFoundError, match="retailpulse ingest"):
        download.read_metadata(tmp_path / "source_metadata.json")


def test_named_queries_are_parsed():
    queries = parse_queries("-- header\n-- name: first\nSELECT 1;\n\n-- name: second\nSELECT 2;\n")

    assert queries == {"first": "SELECT 1", "second": "SELECT 2"}


def test_duplicate_query_names_are_rejected():
    with pytest.raises(ValueError, match="Duplicate query name"):
        parse_queries("-- name: same\nSELECT 1;\n-- name: same\nSELECT 2;\n")


@pytest.mark.parametrize(
    "sql_file", sorted((SQL_DIR / "analysis").glob("*.sql")), ids=lambda p: p.name
)
def test_every_analysis_file_contains_named_queries(sql_file):
    queries = parse_queries(sql_file.read_text(encoding="utf-8"))

    assert queries
    assert all(
        sql.lstrip().upper().startswith(("SELECT", "WITH", "--")) for sql in queries.values()
    )
