import os
import time

import pymysql
from pymysql.cursors import DictCursor


def connect(retries=0, delay=2):
    last_error = None
    for attempt in range(retries + 1):
        try:
            return pymysql.connect(
                host=os.environ.get("DB_HOST", "db"),
                port=int(os.environ.get("DB_PORT", "3306")),
                user=os.environ.get("DB_USER", ""),
                password=os.environ.get("DB_PASSWORD", ""),
                database=os.environ.get("DB_NAME", ""),
                charset="utf8mb4",
                cursorclass=DictCursor,
                autocommit=True,
                connect_timeout=5,
            )
        except pymysql.err.OperationalError as exc:
            last_error = exc
            if attempt < retries:
                time.sleep(delay)
    raise last_error
