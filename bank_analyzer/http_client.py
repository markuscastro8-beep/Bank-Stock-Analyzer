"""HTTP client with retry, polite rate limiting, and SQLite caching.

Used for SEC EDGAR (which requires a descriptive User-Agent) and Yahoo
public endpoints. yfinance has its own session; this client is for raw
JSON / HTML fetches.
"""
from __future__ import annotations

import threading
import time
from dataclasses import dataclass
from typing import Optional

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .cache import Cache
from .logger import get_logger

log = get_logger(__name__)


class _RateLimiter:
    """Simple token-bucket-ish limiter: at most `rate` calls per second."""

    def __init__(self, rate_per_sec: float):
        self._min_interval = 1.0 / max(rate_per_sec, 0.1)
        self._last = 0.0
        self._lock = threading.Lock()

    def wait(self) -> None:
        with self._lock:
            now = time.monotonic()
            delta = now - self._last
            if delta < self._min_interval:
                time.sleep(self._min_interval - delta)
            self._last = time.monotonic()


@dataclass
class FetchResult:
    body: str
    status: int
    from_cache: bool


class HttpClient:
    """Polite HTTP client with caching."""

    def __init__(
        self,
        cache: Cache,
        user_agent: str,
        rate_per_sec: float = 8.0,
        timeout: int = 20,
        max_retries: int = 4,
        backoff_base: float = 1.5,
    ):
        self.cache = cache
        self.timeout = timeout
        self.user_agent = user_agent
        self._limiter = _RateLimiter(rate_per_sec)

        self.session = requests.Session()
        retry = Retry(
            total=max_retries,
            backoff_factor=backoff_base,
            status_forcelist=(429, 500, 502, 503, 504),
            allowed_methods=("GET", "HEAD"),
            raise_on_status=False,
        )
        adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.session.headers.update(
            {
                "User-Agent": user_agent,
                "Accept-Encoding": "gzip, deflate",
            }
        )

    def get(
        self,
        url: str,
        *,
        accept: str = "application/json",
        max_age_sec: Optional[float] = 24 * 3600,
        force_refresh: bool = False,
    ) -> FetchResult:
        """GET a URL, returning cached body when available and fresh."""
        if not force_refresh:
            cached = self.cache.get_http(url, max_age_sec=max_age_sec)
            if cached is not None:
                return FetchResult(body=cached, status=200, from_cache=True)

        self._limiter.wait()
        log.debug("GET %s", url)
        resp = self.session.get(
            url,
            headers={"Accept": accept},
            timeout=self.timeout,
        )
        body = resp.text
        if resp.status_code == 200:
            self.cache.put_http(url, body, resp.status_code)
        else:
            log.warning("GET %s returned %s", url, resp.status_code)
        return FetchResult(body=body, status=resp.status_code, from_cache=False)
