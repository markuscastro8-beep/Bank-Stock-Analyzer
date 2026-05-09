"""Curated universe of US bank tickers for the screener.

Hand-picked rather than auto-generated because:
  * SEC's SIC code 6020/6021/6022 covers thousands of small filers — most are
    not publicly liquid and slow the screener for no benefit.
  * Yahoo's sector/industry classifications are unreliable for thrifts vs.
    commercial banks vs. investment banks.

Each entry is a (ticker, segment) pair. Segments group banks by business
model so users can filter the universe quickly.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BankEntry:
    ticker: str
    segment: str


SEGMENTS = [
    "Money Center",
    "Super-Regional",
    "Regional",
    "Trust & Custody",
    "Investment Bank",
    "Online / Card",
]


UNIVERSE: list[BankEntry] = [
    # --- Money Center (the "big four") ---
    BankEntry("JPM",  "Money Center"),
    BankEntry("BAC",  "Money Center"),
    BankEntry("WFC",  "Money Center"),
    BankEntry("C",    "Money Center"),

    # --- Super-Regional ---
    BankEntry("USB",  "Super-Regional"),
    BankEntry("PNC",  "Super-Regional"),
    BankEntry("TFC",  "Super-Regional"),
    BankEntry("MTB",  "Super-Regional"),
    BankEntry("FITB", "Super-Regional"),
    BankEntry("RF",   "Super-Regional"),
    BankEntry("HBAN", "Super-Regional"),
    BankEntry("KEY",  "Super-Regional"),
    BankEntry("CFG",  "Super-Regional"),
    BankEntry("CMA",  "Super-Regional"),

    # --- Regional ---
    BankEntry("ZION", "Regional"),
    BankEntry("WAL",  "Regional"),
    BankEntry("WBS",  "Regional"),
    BankEntry("EWBC", "Regional"),
    BankEntry("CFR",  "Regional"),
    BankEntry("PB",   "Regional"),
    BankEntry("ONB",  "Regional"),
    BankEntry("UMBF", "Regional"),
    BankEntry("CBSH", "Regional"),
    BankEntry("BOKF", "Regional"),

    # --- Trust & Custody ---
    BankEntry("BK",   "Trust & Custody"),
    BankEntry("STT",  "Trust & Custody"),
    BankEntry("NTRS", "Trust & Custody"),

    # --- Investment Banks (also legally bank holding companies) ---
    BankEntry("GS",   "Investment Bank"),
    BankEntry("MS",   "Investment Bank"),

    # --- Online / Card-focused ---
    BankEntry("COF",  "Online / Card"),
    BankEntry("DFS",  "Online / Card"),
    BankEntry("ALLY", "Online / Card"),
    BankEntry("AXP",  "Online / Card"),
    BankEntry("SYF",  "Online / Card"),
]


def all_tickers() -> list[str]:
    return [b.ticker for b in UNIVERSE]


def by_segment(segment: str) -> list[str]:
    return [b.ticker for b in UNIVERSE if b.segment == segment]


def segment_of(ticker: str) -> str | None:
    for b in UNIVERSE:
        if b.ticker == ticker.upper():
            return b.segment
    return None
