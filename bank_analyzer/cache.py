"""SQLite-backed response cache.

Used for SEC EDGAR JSON responses (rate-limit-friendly) and any other
expensive external calls. Values are stored as TEXT with a fetched-at
timestamp so callers can decide on freshness.
"""
from __future__ import annotations

import json
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Optional

from .logger import get_logger

log = get_logger(__name__)

_SCHEMA = """
CREATE TABLE IF NOT EXISTS http_cache (
    url TEXT PRIMARY KEY,
    body TEXT NOT NULL,
    status INTEGER NOT NULL,
    fetched_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS kv_cache (
    namespace TEXT NOT NULL,
    key TEXT NOT NULL,
    value TEXT NOT NULL,
    fetched_at REAL NOT NULL,
    PRIMARY KEY (namespace, key)
);
"""


class Cache:
    """Tiny SQLite cache. Thread-safe via a single connection lock."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self._conn.executescript(_SCHEMA)
        self._conn.commit()

    # ----- raw HTTP body cache --------------------------------------------------
    def get_http(self, url: str, max_age_sec: Optional[float] = None) -> Optional[str]:
        with self._lock:
            row = self._conn.execute(
                "SELECT body, status, fetched_at FROM http_cache WHERE url = ?",
                (url,),
            ).fetchone()
        if not row:
            return None
        body, status, fetched_at = row
        if status >= 400:
            return None
        if max_age_sec is not None and (time.time() - fetched_at) > max_age_sec:
            return None
        return body

    def put_http(self, url: str, body: str, status: int) -> None:
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO http_cache(url, body, status, fetched_at) "
                "VALUES (?, ?, ?, ?)",
                (url, body, status, time.time()),
            )
            self._conn.commit()

    # ----- arbitrary key/value cache (json-serialized) -------------------------
    def get_json(
        self, namespace: str, key: str, max_age_sec: Optional[float] = None
    ) -> Optional[Any]:
        with self._lock:
            row = self._conn.execute(
                "SELECT value, fetched_at FROM kv_cache WHERE namespace = ? AND key = ?",
                (namespace, key),
            ).fetchone()
        if not row:
            return None
        value, fetched_at = row
        if max_age_sec is not None and (time.time() - fetched_at) > max_age_sec:
            return None
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            log.warning("Cache value for %s/%s is malformed; ignoring", namespace, key)
            return None

    def put_json(self, namespace: str, key: str, value: Any) -> None:
        payload = json.dumps(value, default=str)
        with self._lock:
            self._conn.execute(
                "INSERT OR REPLACE INTO kv_cache(namespace, key, value, fetched_at) "
                "VALUES (?, ?, ?, ?)",
                (namespace, key, payload, time.time()),
            )
            self._conn.commit()

    def close(self) -> None:
        with self._lock:
            self._conn.close()
