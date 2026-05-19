import pytest

from worker.db import connect


@pytest.mark.db
def test_connection_returns_one():
    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT 1")
            row = cur.fetchone()
            assert row == (1,)
