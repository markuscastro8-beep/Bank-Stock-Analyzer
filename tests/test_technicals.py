"""Tests for technical analysis calculations."""
from __future__ import annotations

import numpy as np
import pandas as pd

from bank_analyzer.calculations.technicals import compute_technicals


def _synthetic_history(n: int = 250) -> pd.DataFrame:
    rng = np.random.default_rng(42)
    closes = 100 + np.cumsum(rng.normal(0, 1, size=n))
    df = pd.DataFrame(
        {
            "Open": closes + rng.normal(0, 0.2, size=n),
            "High": closes + np.abs(rng.normal(0, 0.5, size=n)),
            "Low": closes - np.abs(rng.normal(0, 0.5, size=n)),
            "Close": closes,
            "Volume": rng.integers(1_000_000, 5_000_000, size=n),
        },
        index=pd.date_range("2024-01-01", periods=n, freq="B"),
    )
    return df


def test_moving_averages_appended():
    df = _synthetic_history(250)
    res = compute_technicals("FAKE", df, moving_averages=(20, 50, 200))
    assert "MA20" in res.history.columns
    assert "MA50" in res.history.columns
    assert "MA200" in res.history.columns
    assert res.last_close is not None
    assert res.ma_values[20] is not None
    assert res.ma_values[50] is not None
    assert res.ma_values[200] is not None


def test_empty_history_handled():
    res = compute_technicals("FAKE", pd.DataFrame())
    assert res.last_close is None
    assert res.history.empty
