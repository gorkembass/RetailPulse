from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("RETAILPULSE_HOME", Path.cwd())).resolve()

DEFAULT_DATABASE_URL = "postgresql+psycopg://retailpulse:retailpulse@localhost:5432/retailpulse"


@dataclass(frozen=True)
class Paths:
    root: Path = PROJECT_ROOT

    @property
    def raw(self) -> Path:
        return self.root / "data" / "raw"

    @property
    def processed(self) -> Path:
        return self.root / "data" / "processed"

    @property
    def source_metadata(self) -> Path:
        return self.raw / "source_metadata.json"

    @property
    def transactions(self) -> Path:
        return self.processed / "transactions.parquet"

    @property
    def products(self) -> Path:
        return self.processed / "products.parquet"

    @property
    def quality_reports(self) -> Path:
        return self.processed / "quality"

    @property
    def analytics(self) -> Path:
        return self.processed / "analytics"

    @property
    def sql_results(self) -> Path:
        return self.processed / "sql_results"

    @property
    def sql(self) -> Path:
        return self.root / "sql"

    @property
    def dashboard_exports(self) -> Path:
        return self.root / "dashboard" / "exports"


def database_url() -> str:
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)
