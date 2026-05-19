"""Shared fixtures.

`db_conn` opens a real Neon connection wrapped in a SAVEPOINT that is rolled
back after each test, so production data is never mutated.
"""

from collections.abc import Iterator

import psycopg
import pytest

from worker.config import load_settings


class _Rollback(Exception):
    pass


@pytest.fixture
def db_conn() -> Iterator[psycopg.Connection]:
    settings = load_settings()
    conn = psycopg.connect(settings.database_url, autocommit=False)
    try:
        with conn.transaction():
            yield conn
            raise _Rollback
    except _Rollback:
        pass
    finally:
        conn.close()
