"""Curated universe of US bank tickers for the screener.

The "Nano-Cap Community" segment is hand-picked for banks that are typically
**under $300M market cap, with most under $150M**. These are real local
community banks — many trading on OTC or small-cap NASDAQ/NYSE-American — and
they all file 10-Ks with the SEC.

Data caveats for this size band:
  * Yahoo Finance metadata is patchy. Some tickers return no `marketCap`. The
    screener computes a fallback market cap from SEC shares-outstanding × last
    close when Yahoo's is missing.
  * SEC EDGAR XBRL data is reliable for all of them.
  * Failed tickers are skipped gracefully (logged, not crash).

The larger segments (Money Center, Super-Regional, Regional, etc.) are kept
for users who want to compare across the size spectrum.
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BankEntry:
    ticker: str
    segment: str


SEGMENTS = [
    "Nano-Cap Community",
    "Small Community",
    "Money Center",
    "Super-Regional",
    "Regional",
    "Trust & Custody",
    "Investment Bank",
    "Online / Card",
]


UNIVERSE: list[BankEntry] = [
    # =================================================================
    # NANO-CAP COMMUNITY BANKS  — typically <$200M market cap, many <$100M.
    # These are real local community banks and savings institutions.
    # Apply mkt-cap, ROE, ROA filters in the screener to narrow further.
    # =================================================================
    BankEntry("ASRV", "Nano-Cap Community"),  # AmeriServ Financial (PA)
    BankEntry("ATLO", "Nano-Cap Community"),  # Ames National (IA)
    BankEntry("BCBP", "Nano-Cap Community"),  # BCB Bancorp (NJ)
    BankEntry("BPRN", "Nano-Cap Community"),  # The Bank of Princeton (NJ)
    BankEntry("BRBS", "Nano-Cap Community"),  # Blue Ridge Bankshares (VA)
    BankEntry("CARV", "Nano-Cap Community"),  # Carver Bancorp (NY) — Black-owned, NYC
    BankEntry("CCBG", "Nano-Cap Community"),  # Capital City Bank Group (FL)
    BankEntry("CFFI", "Nano-Cap Community"),  # C&F Financial (VA)
    BankEntry("CIVB", "Nano-Cap Community"),  # Civista Bancshares (OH)
    BankEntry("CWBC", "Nano-Cap Community"),  # Community West Bank (CA)
    BankEntry("EBMT", "Nano-Cap Community"),  # Eagle Bancorp Montana
    BankEntry("ESBK", "Nano-Cap Community"),  # Elmira Savings Bank (NY)
    BankEntry("ESSA", "Nano-Cap Community"),  # ESSA Bancorp (PA)
    BankEntry("FCAP", "Nano-Cap Community"),  # First Capital (IN)
    BankEntry("FCCO", "Nano-Cap Community"),  # First Community Corp (SC)
    BankEntry("FFBW", "Nano-Cap Community"),  # FFBW Inc (WI)
    BankEntry("FNCB", "Nano-Cap Community"),  # FNCB Bancorp (PA)
    BankEntry("FRAF", "Nano-Cap Community"),  # Franklin Financial Services (PA)
    BankEntry("FXNC", "Nano-Cap Community"),  # First National Corp (VA)
    BankEntry("GLBZ", "Nano-Cap Community"),  # Glen Burnie Bancorp (MD)
    BankEntry("HFBL", "Nano-Cap Community"),  # Home Federal Bancorp (LA)
    BankEntry("HMNF", "Nano-Cap Community"),  # HMN Financial (MN)
    BankEntry("HWBK", "Nano-Cap Community"),  # Hawthorn Bancshares (MO)
    BankEntry("KFFB", "Nano-Cap Community"),  # Kentucky First Federal Bancorp
    BankEntry("LARK", "Nano-Cap Community"),  # Landmark Bancorp (KS)
    BankEntry("LSBK", "Nano-Cap Community"),  # Lake Shore Bancorp (NY)
    BankEntry("MGYR", "Nano-Cap Community"),  # Magyar Bancorp (NJ)
    BankEntry("NECB", "Nano-Cap Community"),  # Northeast Community Bancorp (NY)
    BankEntry("NWIN", "Nano-Cap Community"),  # Northwest Indiana Bancorp
    BankEntry("OPOF", "Nano-Cap Community"),  # Old Point National (VA)
    BankEntry("OVBC", "Nano-Cap Community"),  # Ohio Valley Financial Group
    BankEntry("PLBC", "Nano-Cap Community"),  # Plumas Bankshares (CA)
    BankEntry("PROV", "Nano-Cap Community"),  # Provident Financial Holdings (CA)
    BankEntry("PVBC", "Nano-Cap Community"),  # Provident Bancorp (MA)
    BankEntry("PWOD", "Nano-Cap Community"),  # Penns Woods Bancorp (PA)
    BankEntry("RIVE", "Nano-Cap Community"),  # Riverview Financial (PA)
    BankEntry("RVSB", "Nano-Cap Community"),  # Riverview Bancorp (WA)
    BankEntry("SHBI", "Nano-Cap Community"),  # Shore Bankshares (MD)
    BankEntry("SMBC", "Nano-Cap Community"),  # Southern Missouri Bancorp
    BankEntry("UNTY", "Nano-Cap Community"),  # Unity Bancorp (NJ)
    BankEntry("VABK", "Nano-Cap Community"),  # Virginia National Financial
    BankEntry("WASH", "Nano-Cap Community"),  # Washington Trust Bancorp (RI)
    BankEntry("WAYN", "Nano-Cap Community"),  # Wayne Savings Bancshares (OH)
    BankEntry("WNEB", "Nano-Cap Community"),  # Western New England Bancorp (MA)
    BankEntry("CZNC", "Nano-Cap Community"),  # Citizens & Northern (PA)
    BankEntry("NWFL", "Nano-Cap Community"),  # Norwood Financial (PA)
    BankEntry("PFIS", "Nano-Cap Community"),  # Peoples Financial Services (PA)
    BankEntry("LCNB", "Nano-Cap Community"),  # LCNB Corp (OH)
    BankEntry("BMRC", "Nano-Cap Community"),  # Bank of Marin (CA)
    BankEntry("NRIM", "Nano-Cap Community"),  # Northrim BanCorp (AK)

    # =================================================================
    # SMALL COMMUNITY  — typically $300M – $2B market cap.
    # =================================================================
    BankEntry("FBMS", "Small Community"),
    BankEntry("MPB",  "Small Community"),
    BankEntry("BHB",  "Small Community"),
    BankEntry("NBN",  "Small Community"),
    BankEntry("MRBK", "Small Community"),
    BankEntry("OSBC", "Small Community"),
    BankEntry("BSRR", "Small Community"),
    BankEntry("FNLC", "Small Community"),
    BankEntry("FCBC", "Small Community"),
    BankEntry("GSBC", "Small Community"),
    BankEntry("HBT",  "Small Community"),
    BankEntry("HMST", "Small Community"),
    BankEntry("KRNY", "Small Community"),
    BankEntry("MCB",  "Small Community"),
    BankEntry("MVBF", "Small Community"),
    BankEntry("NFBK", "Small Community"),
    BankEntry("ORRF", "Small Community"),
    BankEntry("PEBO", "Small Community"),
    BankEntry("QCRH", "Small Community"),
    BankEntry("RBCAA","Small Community"),
    BankEntry("SBSI", "Small Community"),
    BankEntry("SMBK", "Small Community"),
    BankEntry("SRCE", "Small Community"),
    BankEntry("THFF", "Small Community"),
    BankEntry("TMP",  "Small Community"),
    BankEntry("TRMK", "Small Community"),
    BankEntry("UVSP", "Small Community"),
    BankEntry("WSBC", "Small Community"),
    BankEntry("WTBA", "Small Community"),
    BankEntry("CARE", "Small Community"),
    BankEntry("HONE", "Small Community"),
    BankEntry("HBCP", "Small Community"),
    BankEntry("HBNC", "Small Community"),
    BankEntry("ESQ",  "Small Community"),
    BankEntry("CNOB", "Small Community"),
    BankEntry("PCB",  "Small Community"),
    BankEntry("TRST", "Small Community"),

    # =================================================================
    # Money Center
    # =================================================================
    BankEntry("JPM",  "Money Center"),
    BankEntry("BAC",  "Money Center"),
    BankEntry("WFC",  "Money Center"),
    BankEntry("C",    "Money Center"),

    # =================================================================
    # Super-Regional
    # =================================================================
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

    # =================================================================
    # Regional
    # =================================================================
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
    BankEntry("SNV",  "Regional"),
    BankEntry("WAFD", "Regional"),
    BankEntry("WTFC", "Regional"),
    BankEntry("PNFP", "Regional"),
    BankEntry("INDB", "Regional"),
    BankEntry("HTLF", "Regional"),
    BankEntry("SSB",  "Regional"),
    BankEntry("FFIN", "Regional"),
    BankEntry("FFBC", "Regional"),

    # =================================================================
    # Trust & Custody / IBs / Card  (kept for completeness)
    # =================================================================
    BankEntry("BK",   "Trust & Custody"),
    BankEntry("STT",  "Trust & Custody"),
    BankEntry("NTRS", "Trust & Custody"),
    BankEntry("GS",   "Investment Bank"),
    BankEntry("MS",   "Investment Bank"),
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
