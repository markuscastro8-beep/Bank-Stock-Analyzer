"""mplfinance-based PNG candlestick output."""
from __future__ import annotations

from pathlib import Path
from typing import Iterable

import mplfinance as mpf
import pandas as pd

from ..logger import get_logger

log = get_logger(__name__)


def save_candlestick_png(
    history: pd.DataFrame,
    out_path: Path,
    *,
    title: str,
    moving_averages: Iterable[int] = (20, 50, 200),
    show_volume: bool = True,
    days: int = 504,  # ~2 trading years
) -> Path:
    """Render an OHLCV candlestick PNG with MA overlays.

    Returns the path written.
    """
    if history is None or history.empty:
        raise ValueError("history is empty; nothing to chart")

    needed = {"Open", "High", "Low", "Close"}
    if not needed.issubset(history.columns):
        raise ValueError(f"history missing OHLC columns; have {list(history.columns)}")

    df = history.tail(days).copy()
    df.index = pd.to_datetime(df.index)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    style = mpf.make_mpf_style(
        base_mpf_style="charles",
        rc={"figure.figsize": (12, 7)},
    )
    mavs = tuple(int(m) for m in moving_averages)
    addplots = []
    if show_volume and "Volume" not in df.columns:
        show_volume = False

    mpf.plot(
        df,
        type="candle",
        mav=mavs,
        volume=show_volume,
        style=style,
        title=title,
        ylabel="Price",
        ylabel_lower="Volume",
        addplot=addplots,
        savefig=dict(fname=str(out_path), dpi=130, bbox_inches="tight"),
    )
    log.info("Saved candlestick chart to %s", out_path)
    return out_path
