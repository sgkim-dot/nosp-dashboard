from collections.abc import Iterator
from contextlib import contextmanager

import psycopg
from psycopg import Connection

from worker.config import load_settings


@contextmanager
def connect() -> Iterator[Connection]:
    settings = load_settings()
    with psycopg.connect(settings.database_url, autocommit=False) as conn:
        yield conn
