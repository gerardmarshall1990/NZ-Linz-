import contextlib
import psycopg
from psycopg.rows import dict_row
from .config import dsn

@contextlib.contextmanager
def conn():
    with psycopg.connect(dsn(), row_factory=dict_row) as c:
        yield c
