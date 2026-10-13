from __future__ import annotations

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import Engine, create_engine

from retailpulse.config import database_url


def get_engine(url: str | None = None) -> Engine:
    return create_engine(url or database_url(), pool_pre_ping=True)


@contextmanager
def driver_cursor(engine: Engine) -> Iterator:
    """Yield a psycopg cursor inside a transaction that commits on success."""
    connection = engine.raw_connection()
    try:
        with connection.cursor() as cursor:
            yield cursor
        connection.commit()
    except Exception:
        connection.rollback()
        raise
    finally:
        connection.close()


def run_script(engine: Engine, path: Path) -> None:
    """Execute a multi-statement SQL file in a single transaction."""
    with driver_cursor(engine) as cursor:
        cursor.execute(path.read_text(encoding="utf-8"))
