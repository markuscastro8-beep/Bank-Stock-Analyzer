"""Top-level orchestration.

The `Analyzer` builds a fully-populated `AnalysisResult` for one ticker by
coordinating the data sources, parsers, and calculation modules. Heavy
lifting (HTTP, cache, retries) is delegated to the lower-level modules.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from .calculations.fundamentals import FundamentalsResult, compute_fundamentals
from .calculations.technicals import TechnicalsResult, compute_technicals
from .cache import Cache
from .config import Config, load_config
from .data_sources import SecEdgarClient, SeekingAlphaClient, YahooFinanceClient
from .data_sources.sec_edgar import SecCompanyData
from .http_client import HttpClient
from .logger import get_logger, setup_logging
from .sec_parser.filing_parser import FallbackHit, RawFilingFallback

log = get_logger(__name__)


@dataclass
class AnalysisResult:
    ticker: str
    company_name: str
    sec: SecCompanyData
    fundamentals: FundamentalsResult
    technicals: TechnicalsResult
    yahoo_info: dict = field(default_factory=dict)
    seeking_alpha_link: str = ""
    seeking_alpha_headlines: list = field(default_factory=list)
    extras: dict = field(default_factory=dict)


class Analyzer:
    """Façade that produces an `AnalysisResult` for a ticker."""

    def __init__(self, config: Optional[Config] = None):
        self.config = config or load_config()
        setup_logging(self.config.log_dir, self.config.log_level)
        self.cache = Cache(self.config.cache_db)
        self.sec_http = HttpClient(
            self.cache,
            user_agent=self.config.sec_user_agent,
            rate_per_sec=self.config.sec_rate_limit_per_sec,
            timeout=self.config.request_timeout_sec,
            max_retries=self.config.max_retries,
            backoff_base=self.config.backoff_base_sec,
        )
        self.public_http = HttpClient(
            self.cache,
            user_agent=self.config.sec_user_agent,
            rate_per_sec=self.config.yahoo_rate_limit_per_sec,
            timeout=self.config.request_timeout_sec,
            max_retries=self.config.max_retries,
            backoff_base=self.config.backoff_base_sec,
        )
        self.sec = SecEdgarClient(self.sec_http, self.cache)
        self.yahoo = YahooFinanceClient(self.cache)
        self.seeking_alpha = SeekingAlphaClient(self.public_http, self.cache)

    # ---------------------------------------------------------------- validate
    def validate_ticker(self, ticker: str) -> tuple[bool, str]:
        """Return (ok, reason). Combines SEC registry + Yahoo sanity check."""
        ticker = ticker.strip().upper()
        if not ticker:
            return False, "empty ticker"
        if not all(c.isalnum() or c in ".-" for c in ticker):
            return False, f"ticker {ticker!r} contains invalid characters"
        try:
            self.sec.lookup_ticker(ticker)
        except ValueError as exc:
            return False, str(exc)
        if not self.yahoo.validate_ticker(ticker):
            return False, "Yahoo Finance returned no price history"
        return True, ""

    # ---------------------------------------------------------------- analyze
    def analyze(self, ticker: str) -> AnalysisResult:
        ticker = ticker.strip().upper()
        log.info("Analyzing %s", ticker)

        sec_data = self.sec.gather(ticker, fiscal_years=self.config.fiscal_years)
        log.info(
            "SEC: %s (CIK %s) — %d 10-K filings, %d company facts",
            sec_data.info.name,
            sec_data.info.cik10,
            len(sec_data.filings_10k),
            len(sec_data.company_facts.get("facts", {}).get("us-gaap", {})),
        )

        snapshot = self.yahoo.snapshot(ticker, years=self.config.price_history_years)
        log.info(
            "Yahoo: %d days of price history, last close %s",
            len(snapshot.history),
            snapshot.last_close,
        )

        fundamentals = compute_fundamentals(
            ticker=ticker,
            company_facts=sec_data.company_facts,
            fiscal_years=self.config.fiscal_years,
        )
        technicals = compute_technicals(
            ticker=ticker,
            history=snapshot.history,
            moving_averages=self.config.moving_averages,
        )

        # CET1 ratio is rarely tagged consistently in XBRL; try a regex over the
        # latest 10-K primary document as a best-effort fallback.
        extras: dict = {}
        try:
            cet1_hit = self._fallback_cet1(sec_data)
            if cet1_hit:
                extras["cet1_ratio"] = cet1_hit.value
                extras["cet1_excerpt"] = cet1_hit.excerpt
        except Exception as exc:  # noqa: BLE001
            log.debug("CET1 fallback skipped: %s", exc)

        # Seeking Alpha — public data only.
        sa_link = self.seeking_alpha.article_link(ticker)
        sa_headlines = self.seeking_alpha.news_rss(ticker)

        result = AnalysisResult(
            ticker=ticker,
            company_name=sec_data.info.name,
            sec=sec_data,
            fundamentals=fundamentals,
            technicals=technicals,
            yahoo_info=snapshot.info,
            seeking_alpha_link=sa_link,
            seeking_alpha_headlines=sa_headlines,
            extras=extras,
        )
        return result

    def _fallback_cet1(self, sec_data: SecCompanyData) -> Optional[FallbackHit]:
        if not sec_data.filings_10k:
            return None
        latest = sec_data.filings_10k[0]
        html = self.sec.fetch_filing_text(latest)
        if not html:
            return None
        return RawFilingFallback(html).find_cet1_ratio()

    # ---------------------------------------------------------------- peers
    def compare_peers(self, ticker: str, peers: list[str]) -> dict:
        """Return a dict of ticker -> AnalysisResult-light for peer comparison."""
        all_tickers = [ticker.upper(), *[p.upper() for p in peers if p.upper() != ticker.upper()]]
        results = {}
        for t in all_tickers:
            try:
                results[t] = self.analyze(t)
            except Exception as exc:  # noqa: BLE001
                log.warning("Peer analysis failed for %s: %s", t, exc)
        return results

    # ---------------------------------------------------------------- shutdown
    def close(self) -> None:
        self.cache.close()
