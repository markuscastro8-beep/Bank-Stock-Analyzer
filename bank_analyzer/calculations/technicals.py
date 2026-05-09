"""Technical analysis: moving averages and price summaries."""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import pandas as pd


@dataclass
class TechnicalsResult:
    ticker: str
    history: pd.DataFrame  # OHLCV with MA columns appended
    last_close: Optional[float] = None
    high_52w: Optional[float] = None
    low_52w: Optional[float] = None
    ma_values: dict[int, Optional[float]] = field(default_factory=dict)


def compute_technicals(
    ticker: str,
    history: pd.DataFrame,
    moving_averages: tuple[int, ...] = (20, 50, 200),
) -> TechnicalsResult:
    if history is None or history.empty:
        return TechnicalsResult(ticker=ticker.upper(), history=pd.DataFrame())

    df = history.copy()
    if "Close" not in df.columns:
        raise ValueError("history must contain a 'Close' column")

    for window in moving_averages:
        df[f"MA{window}"] = df["Close"].rolling(window=window, min_periods=window).mean()

    last_close = float(df["Close"].iloc[-1])

    last_year = df.tail(252)
    high_52w = float(last_year["High"].max()) if "High" in df.columns else None
    low_52w = float(last_year["Low"].min()) if "Low" in df.columns else None

    ma_values: dict[int, Optional[float]] = {}
    for window in moving_averages:
        col = f"MA{window}"
        val = df[col].iloc[-1]
        ma_values[window] = float(val) if pd.notna(val) else None

    return TechnicalsResult(
        ticker=ticker.upper(),
        history=df,
        last_close=last_close,
        high_52w=high_52w,
        low_52w=low_52w,
        ma_values=ma_values,
    )
