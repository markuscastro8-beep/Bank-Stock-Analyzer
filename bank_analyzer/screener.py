"""Bank screener — runs the analyzer across a universe in parallel.

Returns a tidy DataFrame with one row per ticker and the metrics most
useful for cross-sectional comparison: market cap, valuation multiples
(P/E, P/B, P/TBV), profitability (ROE, ROA), growth (EPS YoY), dividend
yield, capital strength (CET1 if available), and price-vs-MA position.

Designed to be polite to upstream APIs (cache-aware, modest concurrency).
A single screener run over ~35 banks with cold caches takes ~30–60s; with
warm caches it's near-instant.
"""
from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from typing import Callable, Optional

import pandas as pd

from .analyzer import AnalysisResult, Analyzer
from .logger import get_logger

log = get_logger(__name__)


@dataclass
class ScreenerRow:
    ticker: str
    company_name: str
    segment: Optional[str]
    last_close: Optional[float]
    market_cap: Optional[float]
    ttm_eps: Optional[float]
    pe_ttm: Optional[float]
    pb: Optional[float]
    p_tbv: Optional[float]
    roe: Optional[float]
    roa: Optional[float]
    eps_growth_yoy: Optional[float]
    dividend_yield: Optional[float]
    book_value_per_share: Optional[float]
    tbv_per_share: Optional[float]
    total_assets: Optional[float]
    common_equity: Optional[float]
    high_52w: Optional[float]
    low_52w: Optional[float]
    pct_off_high_52w: Optional[float]
    cet1_ratio: Optional[float]
    ma50: Optional[float]
    ma200: Optional[float]
    above_ma200: Optional[bool]


def _row_from_result(result: AnalysisResult, segment: Optional[str]) -> ScreenerRow:
    fund = result.fundamentals
    tech = result.technicals
    latest = fund.latest
    info = result.yahoo_info or {}

    last_close = tech.last_close
    pe_ttm = (last_close / fund.ttm_eps) if (last_close and fund.ttm_eps) else None
    pb = (
        last_close / latest.book_value_per_share
        if (last_close and latest and latest.book_value_per_share)
        else None
    )
    p_tbv = (
        last_close / latest.tangible_book_value_per_share
        if (last_close and latest and latest.tangible_book_value_per_share)
        else None
    )
    pct_off_high = (
        (last_close - tech.high_52w) / tech.high_52w
        if (last_close and tech.high_52w)
        else None
    )

    ma200 = tech.ma_values.get(200)
    above_ma200 = (last_close > ma200) if (last_close is not None and ma200 is not None) else None

    # Market cap fallback: Yahoo metadata is sparse for thinly-traded micro-caps.
    # If Yahoo didn't return marketCap, derive it from SEC's most recent
    # end-of-period shares outstanding × last close. Less timely but accurate
    # within ~1 reporting cycle, and far better than dropping the row entirely.
    market_cap = info.get("marketCap")
    if market_cap is None and last_close is not None and latest is not None and latest.shares_eop:
        market_cap = float(last_close) * float(latest.shares_eop)

    return ScreenerRow(
        ticker=result.ticker,
        company_name=result.company_name,
        segment=segment,
        last_close=last_close,
        market_cap=market_cap,
        ttm_eps=fund.ttm_eps,
        pe_ttm=pe_ttm,
        pb=pb,
        p_tbv=p_tbv,
        roe=latest.roe if latest else None,
        roa=latest.roa if latest else None,
        eps_growth_yoy=latest.eps_growth if latest else None,
        dividend_yield=info.get("dividendYield"),
        book_value_per_share=latest.book_value_per_share if latest else None,
        tbv_per_share=latest.tangible_book_value_per_share if latest else None,
        total_assets=latest.total_assets if latest else None,
        common_equity=latest.common_equity if latest else None,
        high_52w=tech.high_52w,
        low_52w=tech.low_52w,
        pct_off_high_52w=pct_off_high,
        cet1_ratio=result.extras.get("cet1_ratio"),
        ma50=tech.ma_values.get(50),
        ma200=ma200,
        above_ma200=above_ma200,
    )


def run_screener(
    analyzer: Analyzer,
    tickers: list[str],
    segment_lookup: Optional[Callable[[str], Optional[str]]] = None,
    max_workers: int = 6,
    progress: Optional[Callable[[int, int, str], None]] = None,
) -> pd.DataFrame:
    """Run the analyzer across `tickers` in parallel and return a DataFrame.

    `progress(done, total, current_ticker)` is invoked after each ticker
    completes — wire it to a Streamlit progress bar if you want a UI.
    Failed tickers are logged and skipped; the screener keeps going.
    """
    rows: list[ScreenerRow] = []
    total = len(tickers)
    completed = 0

    def _one(ticker: str) -> Optional[ScreenerRow]:
        try:
            result = analyzer.analyze(ticker)
            seg = segment_lookup(ticker) if segment_lookup else None
            return _row_from_result(result, seg)
        except Exception as exc:  # noqa: BLE001
            log.warning("Screener: skipping %s (%s)", ticker, exc)
            return None

    with ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {pool.submit(_one, t): t for t in tickers}
        for fut in as_completed(futures):
            ticker = futures[fut]
            row = fut.result()
            completed += 1
            if progress:
                progress(completed, total, ticker)
            if row is not None:
                rows.append(row)

    if not rows:
        return pd.DataFrame()

    df = pd.DataFrame([r.__dict__ for r in rows])
    df = df.sort_values("market_cap", ascending=False, na_position="last").reset_index(drop=True)
    return df
