"""Yahoo Finance client (yfinance wrapper).

Wraps yfinance to provide retries, caching of frequently-requested
metadata, and a stable return shape. yfinance scrapes Yahoo's public
endpoints; we stay polite by limiting the request volume and respecting
yfinance's own rate limiting.
"""
from __future__ import annotations

import time
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any, Optional

import pandas as pd
import yfinance as yf

from ..cache import Cache
from ..logger import get_logger

log = get_logger(__name__)


@dataclass
class YahooSnapshot:
    ticker: str
    info: dict[str, Any]
    history: pd.DataFrame
    dividends: pd.Series

    @property
    def last_close(self) -> Optional[float]:
        if self.history is None or self.history.empty:
            return None
        return float(self.history["Close"].iloc[-1])


class YahooFinanceClient:
    """Thin yfinance wrapper with caching + retry."""

    def __init__(
        self,
        cache: Cache,
        max_retries: int = 3,
        backoff_base: float = 1.5,
    ):
        self.cache = cache
        self.max_retries = max_retries
        self.backoff_base = backoff_base

    # ------------------------------------------------------------- validation
    def validate_ticker(self, ticker: str) -> bool:
        """Quick sanity check that yfinance recognizes the ticker."""
        ticker = ticker.strip().upper()
        if not ticker:
            return False
        try:
            t = yf.Ticker(ticker)
            hist = t.history(period="5d")
            return hist is not None and not hist.empty
        except Exception as exc:  # noqa: BLE001
            log.warning("Yahoo validation failed for %s: %s", ticker, exc)
            return False

    # ------------------------------------------------------------- price history
    def fetch_history(self, ticker: str, years: int = 5) -> pd.DataFrame:
        ticker = ticker.upper()
        cache_key = f"history:{ticker}:{years}y"
        cached = self.cache.get_json("yahoo", cache_key, max_age_sec=12 * 3600)
        if cached:
            df = pd.DataFrame(cached)
            if "Date" in df.columns:
                df["Date"] = pd.to_datetime(df["Date"])
                df = df.set_index("Date")
            return df

        end = datetime.utcnow()
        start = end - timedelta(days=int(365.25 * years) + 7)

        last_err: Optional[Exception] = None
        for attempt in range(self.max_retries):
            try:
                t = yf.Ticker(ticker)
                df = t.history(
                    start=start.strftime("%Y-%m-%d"),
                    end=end.strftime("%Y-%m-%d"),
                    auto_adjust=False,
                    actions=True,
                )
                if df is None or df.empty:
                    raise RuntimeError("empty history")
                df = df.dropna(how="all")
                # Cache as records.
                df_reset = df.reset_index().copy()
                df_reset["Date"] = df_reset["Date"].astype(str)
                self.cache.put_json("yahoo", cache_key, df_reset.to_dict(orient="records"))
                return df
            except Exception as exc:  # noqa: BLE001
                last_err = exc
                wait = self.backoff_base ** attempt
                log.warning("yfinance history attempt %s failed: %s (retry in %.1fs)", attempt + 1, exc, wait)
                time.sleep(wait)
        raise RuntimeError(f"Failed to fetch history for {ticker}: {last_err}")

    # ------------------------------------------------------------- info / metadata
    def fetch_info(self, ticker: str) -> dict[str, Any]:
        ticker = ticker.upper()
        cached = self.cache.get_json("yahoo", f"info:{ticker}", max_age_sec=6 * 3600)
        if cached:
            return cached

        for attempt in range(self.max_retries):
            try:
                t = yf.Ticker(ticker)
                info = dict(t.info or {})
                if not info:
                    raise RuntimeError("empty info")
                self.cache.put_json("yahoo", f"info:{ticker}", info)
                return info
            except Exception as exc:  # noqa: BLE001
                wait = self.backoff_base ** attempt
                log.warning("yfinance info attempt %s failed: %s", attempt + 1, exc)
                time.sleep(wait)
        return {}

    # ------------------------------------------------------------- dividends
    def fetch_dividends(self, ticker: str) -> pd.Series:
        ticker = ticker.upper()
        try:
            t = yf.Ticker(ticker)
            return t.dividends
        except Exception as exc:  # noqa: BLE001
            log.warning("yfinance dividends fetch failed for %s: %s", ticker, exc)
            return pd.Series(dtype=float)

    # ------------------------------------------------------------- aggregate
    def snapshot(self, ticker: str, years: int = 5) -> YahooSnapshot:
        info = self.fetch_info(ticker)
        history = self.fetch_history(ticker, years=years)
        divs = self.fetch_dividends(ticker)
        return YahooSnapshot(ticker=ticker.upper(), info=info, history=history, dividends=divs)
