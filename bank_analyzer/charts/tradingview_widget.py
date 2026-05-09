"""TradingView Advanced Chart widget HTML embed.

TradingView publishes free embeddable chart widgets at
https://www.tradingview.com/widget/. They are public, require no API key,
and are intended for embedding on third-party sites — Streamlit included.

This module builds the HTML for the Advanced Chart widget pre-configured
with three moving averages (20, 50, 200 SMA), volume, and a clean theme.
"""
from __future__ import annotations

import json
from typing import Iterable, Literal


# Best-effort exchange mapping for US bank tickers we care about.
# TradingView accepts a bare ticker too — these prefixes just remove
# any ambiguity (e.g. "C" can collide with foreign listings).
_NYSE = {"JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "BK", "STT",
         "NTRS", "RF", "MTB", "FITB", "KEY", "HBAN", "CMA"}
_NASDAQ = {"SIVB", "ZION", "WAL", "PACW", "SBNY"}


def qualify_symbol(ticker: str) -> str:
    """Add an exchange prefix if we can confidently identify one."""
    t = ticker.strip().upper()
    if ":" in t:
        return t
    if t in _NYSE:
        return f"NYSE:{t}"
    if t in _NASDAQ:
        return f"NASDAQ:{t}"
    return t  # let TradingView's default resolver handle it


def advanced_chart_html(
    ticker: str,
    *,
    theme: Literal["light", "dark"] = "light",
    interval: str = "D",
    height: int = 600,
    moving_averages: Iterable[int] = (20, 50, 200),
) -> str:
    """Return a self-contained HTML string with the TradingView Advanced Chart.

    Drops in cleanly to `streamlit.components.v1.html(html, height=...)`.
    """
    symbol = qualify_symbol(ticker)
    studies = []
    # TradingView's MA study ID is "MASimple@tv-basicstudies"; we add one per length.
    for length in moving_averages:
        studies.append(
            {
                "id": "MASimple@tv-basicstudies",
                "inputs": {"length": int(length)},
            }
        )

    config = {
        "autosize": True,
        "symbol": symbol,
        "interval": interval,
        "timezone": "Etc/UTC",
        "theme": theme,
        "style": "1",  # candles
        "locale": "en",
        "enable_publishing": False,
        "withdateranges": True,
        "hide_side_toolbar": False,
        "allow_symbol_change": True,
        "details": True,
        "calendar": False,
        "studies": studies,
        "support_host": "https://www.tradingview.com",
    }

    config_json = json.dumps(config)
    return f"""
    <div class="tradingview-widget-container" style="height:{height}px;width:100%;">
      <div class="tradingview-widget-container__widget"
           style="height:calc(100% - 32px);width:100%;"></div>
      <div class="tradingview-widget-copyright" style="font-size:11px;color:#9db2bd;">
        <a href="https://www.tradingview.com/" rel="noopener nofollow" target="_blank">
          Track all markets on TradingView
        </a>
      </div>
      <script type="text/javascript"
              src="https://s3.tradingview.com/external-embedding/embed-widget-advanced-chart.js"
              async>
        {config_json}
      </script>
    </div>
    """


def mini_chart_html(ticker: str, *, theme: str = "light", height: int = 220) -> str:
    """Smaller TradingView mini-chart, useful for peer comparison cards."""
    symbol = qualify_symbol(ticker)
    config = {
        "symbol": symbol,
        "width": "100%",
        "height": height,
        "locale": "en",
        "dateRange": "12M",
        "colorTheme": theme,
        "isTransparent": False,
        "autosize": True,
        "largeChartUrl": "",
    }
    return f"""
    <div class="tradingview-widget-container" style="height:{height}px;width:100%;">
      <div class="tradingview-widget-container__widget"></div>
      <script type="text/javascript"
              src="https://s3.tradingview.com/external-embedding/embed-widget-mini-symbol-overview.js"
              async>
        {json.dumps(config)}
      </script>
    </div>
    """
