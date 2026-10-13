from __future__ import annotations

import logging
import re
from decimal import Decimal
from pathlib import Path

import pandas as pd
from sqlalchemy import Engine

from retailpulse.database.connection import driver_cursor

logger = logging.getLogger(__name__)

_NAME_MARKER = re.compile(r"^--\s*name:\s*(?P<name>[a-z0-9_]+)\s*$", re.MULTILINE)


def parse_queries(sql_text: str) -> dict[str, str]:
    """Split a SQL file into named queries delimited by ``-- name: <identifier>`` lines."""
    matches = list(_NAME_MARKER.finditer(sql_text))
    queries: dict[str, str] = {}
    for position, match in enumerate(matches):
        end = matches[position + 1].start() if position + 1 < len(matches) else len(sql_text)
        body = sql_text[match.end() : end].strip().rstrip(";").strip()
        name = match.group("name")
        if name in queries:
            raise ValueError(f"Duplicate query name '{name}'")
        if body:
            queries[name] = body
    return queries


def load_queries(path: Path) -> dict[str, str]:
    return parse_queries(path.read_text(encoding="utf-8"))


def run_query(engine: Engine, sql: str) -> pd.DataFrame:
    """Run a query and return a DataFrame, mapping NUMERIC to int64 or float64 by its scale."""
    with driver_cursor(engine) as cursor:
        cursor.execute(sql)
        columns = [column.name for column in cursor.description]
        frame = pd.DataFrame(cursor.fetchall(), columns=columns)
    for column in frame.columns:
        decimals = [value for value in frame[column] if isinstance(value, Decimal)]
        if not decimals:
            continue
        has_scale = any(value.as_tuple().exponent < 0 for value in decimals)
        if has_scale or frame[column].isna().any():
            frame[column] = frame[column].astype("float64")
        else:
            frame[column] = frame[column].astype("int64")
    return frame


def run_analysis_files(engine: Engine, analysis_dir: Path, output_dir: Path) -> list[Path]:
    """Run every named query under ``analysis_dir`` and write one CSV per query."""
    output_dir.mkdir(parents=True, exist_ok=True)
    written = []
    for sql_file in sorted(analysis_dir.glob("*.sql")):
        for name, sql in load_queries(sql_file).items():
            result = run_query(engine, sql)
            target = output_dir / f"{sql_file.stem}__{name}.csv"
            result.to_csv(target, index=False)
            written.append(target)
            logger.info("%s: %s -> %d rows", sql_file.name, name, len(result))
    return written
