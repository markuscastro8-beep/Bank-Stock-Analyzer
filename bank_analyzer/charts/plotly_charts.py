"""Plotly + TradingView lightweight-charts payload generation.

`build_plotly_chart` returns a Plotly Figure suitable for inline display
or HTML export.

`lightweight_chart_payload` returns a dict ready to feed to the
TradingView Lightweight Charts JS library (https://github.com/tradingview
/lightweight-charts) — the same wire format consumed by the
`lightweight-charts` Python wrapper if you choose to render in a desktop
window. We do not import that wrapper here because it is optional.
"""
from __future__ import annotations

from typing import Any, Iterable

import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots


def build_plotly_chart(
    history: pd.DataFrame,
    *,
    title: str,
    moving_averages: Iterable[int] = (20, 50, 200),
) -> go.Figure:
    df = history.copy()
    df.index = pd.to_datetime(df.index)

    fig = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.03,
        row_heights=[0.75, 0.25],
        subplot_titles=(title, "Volume"),
    )
    fig.add_trace(
        go.Candlestick(
            x=df.index,
            open=df["Open"],
            high=df["High"],
            low=df["Low"],
            close=df["Close"],
            name="OHLC",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    for window in moving_averages:
        col_name = f"MA{window}"
        if col_name not in df.columns:
            df[col_name] = df["Close"].rolling(window=window, min_periods=window).mean()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df[col_name],
                mode="lines",
                name=f"MA{window}",
            ),
            row=1,
            col=1,
        )
    if "Volume" in df.columns:
        fig.add_trace(
            go.Bar(
                x=df.index,
                y=df["Volume"],
                name="Volume",
                showlegend=False,
                marker_line_width=0,
            ),
            row=2,
            col=1,
        )

    fig.update_layout(
        height=750,
        xaxis_rangeslider_visible=False,
        template="plotly_white",
        margin=dict(l=40, r=20, t=60, b=30),
    )
    return fig


def lightweight_chart_payload(
    history: pd.DataFrame,
    *,
    moving_averages: Iterable[int] = (20, 50, 200),
) -> dict[str, Any]:
    """Build a JSON-serializable payload for TradingView lightweight-charts."""
    df = history.copy()
    df.index = pd.to_datetime(df.index)

    candles = [
        {
            "time": ts.strftime("%Y-%m-%d"),
            "open": float(row["Open"]),
            "high": float(row["High"]),
            "low": float(row["Low"]),
            "close": float(row["Close"]),
        }
        for ts, row in df.iterrows()
        if pd.notna(row["Open"])
    ]
    volume = []
    if "Volume" in df.columns:
        volume = [
            {
                "time": ts.strftime("%Y-%m-%d"),
                "value": float(row["Volume"]) if pd.notna(row["Volume"]) else 0.0,
                "color": "#26a69a" if row["Close"] >= row["Open"] else "#ef5350",
            }
            for ts, row in df.iterrows()
            if pd.notna(row["Close"])
        ]
    ma_series = {}
    for window in moving_averages:
        col = f"MA{window}"
        if col not in df.columns:
            df[col] = df["Close"].rolling(window=window, min_periods=window).mean()
        ma_series[col] = [
            {"time": ts.strftime("%Y-%m-%d"), "value": float(v)}
            for ts, v in df[col].items()
            if pd.notna(v)
        ]
    return {"candles": candles, "volume": volume, "moving_averages": ma_series}
