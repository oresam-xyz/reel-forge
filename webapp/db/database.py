"""PostgreSQL connection pool and helpers."""

from __future__ import annotations

import os
from contextlib import contextmanager
from pathlib import Path

import psycopg2
import psycopg2.extras
from psycopg2.pool import SimpleConnectionPool

_pool: SimpleConnectionPool | None = None


def init_db(dsn: str | None = None) -> None:
    global _pool
    dsn = dsn or os.environ["DATABASE_URL"]
    _pool = SimpleConnectionPool(minconn=1, maxconn=10, dsn=dsn)

    schema = Path(__file__).parent / "schema.sql"
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(schema.read_text())
        conn.commit()


@contextmanager
def get_db():
    if _pool is None:
        raise RuntimeError("Database not initialised — call init_db() first")
    conn = _pool.getconn()
    conn.cursor_factory = psycopg2.extras.RealDictCursor
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    finally:
        _pool.putconn(conn)
