"""Bank-specific fundamental calculations.

All metrics are computed per fiscal year using point-in-time XBRL values
from the companyfacts payload. Where a bank-specific concept is missing,
we fall back to general us-gaap concepts and clearly mark approximations.

Metric definitions (see README for sourcing assumptions):

    EPS_basic     = NetIncomeLossAvailableToCommonStockholdersBasic
                    / WeightedAverageNumberOfSharesOutstandingBasic
                    (preferred when reported; otherwise reported EarningsPerShareBasic)
    EPS_diluted   = analogous, diluted shares
    EPS_growth    = (EPS_t / EPS_{t-1}) - 1
    BV/share      = CommonEquity / SharesOutstandingEoP
    TBV/share     = (CommonEquity − Goodwill − OtherIntangibles) / SharesOutstandingEoP
    ROE           = NetIncomeToCommon / AvgCommonEquity        (avg of beginning/ending)
    ROA           = NetIncome / AvgTotalAssets

`AvgX = (X_t + X_{t-1}) / 2` when both available, else `X_t`.

TTM EPS is computed from quarterly companyfacts data when available;
otherwise we fall back to the most recent annual EPS as TTM.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Optional

from ..logger import get_logger
from ..sec_parser.xbrl_parser import FactSeries, XbrlFactExtractor

log = get_logger(__name__)


@dataclass
class YearMetrics:
    fiscal_year: int
    period_end: str
    net_income: Optional[float] = None
    net_income_to_common: Optional[float] = None
    common_equity: Optional[float] = None
    preferred_equity: Optional[float] = None
    total_assets: Optional[float] = None
    goodwill: Optional[float] = None
    intangibles: Optional[float] = None
    shares_eop: Optional[float] = None
    weighted_shares_basic: Optional[float] = None
    weighted_shares_diluted: Optional[float] = None
    eps_basic_reported: Optional[float] = None
    eps_diluted_reported: Optional[float] = None
    dividends_per_share: Optional[float] = None

    # derived
    eps_basic: Optional[float] = None
    eps_diluted: Optional[float] = None
    eps_growth: Optional[float] = None
    book_value_per_share: Optional[float] = None
    tangible_book_value_per_share: Optional[float] = None
    roe: Optional[float] = None
    roa: Optional[float] = None


@dataclass
class FundamentalsResult:
    ticker: str
    years: list[YearMetrics] = field(default_factory=list)
    ttm_eps: Optional[float] = None
    eps_12: Optional[float] = None  # alias for "EPS 12" (TTM)
    notes: list[str] = field(default_factory=list)

    @property
    def latest(self) -> Optional[YearMetrics]:
        return self.years[0] if self.years else None


# ---------------------------------------------------------------------------
def _val_for_year(series: FactSeries, fy: int) -> Optional[float]:
    pt = series.by_fy().get(fy)
    return pt.val if pt else None


def _safe_div(numerator: Optional[float], denom: Optional[float]) -> Optional[float]:
    if numerator is None or denom is None:
        return None
    if denom == 0 or math.isclose(denom, 0):
        return None
    return numerator / denom


def _avg(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None and b is None:
        return None
    if a is None:
        return b
    if b is None:
        return a
    return (a + b) / 2.0


def compute_fundamentals(
    ticker: str,
    company_facts: dict,
    fiscal_years: int = 3,
) -> FundamentalsResult:
    """Build per-year metrics from companyfacts XBRL data."""
    ext = XbrlFactExtractor(company_facts)

    metric_keys = [
        "net_income",
        "net_income_to_common",
        "common_equity",
        "stockholders_equity",
        "preferred_equity",
        "total_assets",
        "goodwill",
        "intangibles_ex_goodwill",
        "shares_outstanding_eop",
        "weighted_avg_shares_basic",
        "weighted_avg_shares_diluted",
        "eps_basic",
        "eps_diluted",
        "dividends_per_share",
    ]
    series = ext.extract_many(metric_keys)
    notes: list[str] = []

    # Discover the set of fiscal years that appear in the most-likely-to-be-present
    # series (net income), then take the most recent N.
    candidate_fys: set[int] = set()
    for s in series.values():
        for p in s.points:
            if p.fy is not None:
                candidate_fys.add(p.fy)

    if not candidate_fys:
        notes.append("No annual XBRL fiscal-year tagged data found.")
        return FundamentalsResult(ticker=ticker, years=[], notes=notes)

    selected = sorted(candidate_fys, reverse=True)[:fiscal_years]
    # Need one extra year before the earliest for averages and EPS growth.
    avg_anchor_fy = (min(selected) - 1) if selected else None

    years: list[YearMetrics] = []
    for fy in selected:
        # Resolve a period-end label.
        ni_pt = series["net_income"].by_fy().get(fy)
        period_end = ni_pt.end if ni_pt else f"{fy}-12-31"

        # Common equity: prefer explicit CommonStockholdersEquity, else fall back
        # to total stockholders' equity minus preferred (if both available).
        common_equity = _val_for_year(series["common_equity"], fy)
        if common_equity is None:
            tot_eq = _val_for_year(series["stockholders_equity"], fy)
            pref = _val_for_year(series["preferred_equity"], fy)
            if tot_eq is not None and pref is not None:
                common_equity = tot_eq - pref
                notes.append(
                    f"FY{fy}: derived common equity = stockholders' equity − preferred."
                )
            elif tot_eq is not None:
                common_equity = tot_eq
                notes.append(
                    f"FY{fy}: using total stockholders' equity as common equity proxy."
                )

        ym = YearMetrics(
            fiscal_year=fy,
            period_end=period_end,
            net_income=_val_for_year(series["net_income"], fy),
            net_income_to_common=_val_for_year(series["net_income_to_common"], fy),
            common_equity=common_equity,
            preferred_equity=_val_for_year(series["preferred_equity"], fy),
            total_assets=_val_for_year(series["total_assets"], fy),
            goodwill=_val_for_year(series["goodwill"], fy),
            intangibles=_val_for_year(series["intangibles_ex_goodwill"], fy),
            shares_eop=_val_for_year(series["shares_outstanding_eop"], fy),
            weighted_shares_basic=_val_for_year(series["weighted_avg_shares_basic"], fy),
            weighted_shares_diluted=_val_for_year(series["weighted_avg_shares_diluted"], fy),
            eps_basic_reported=_val_for_year(series["eps_basic"], fy),
            eps_diluted_reported=_val_for_year(series["eps_diluted"], fy),
            dividends_per_share=_val_for_year(series["dividends_per_share"], fy),
        )

        # Derived: EPS — prefer reported tagged EPS, else compute.
        ym.eps_basic = ym.eps_basic_reported or _safe_div(
            ym.net_income_to_common or ym.net_income, ym.weighted_shares_basic
        )
        ym.eps_diluted = ym.eps_diluted_reported or _safe_div(
            ym.net_income_to_common or ym.net_income, ym.weighted_shares_diluted
        )

        # Book value / TBV per share (use end-of-period shares).
        ym.book_value_per_share = _safe_div(ym.common_equity, ym.shares_eop)
        if ym.common_equity is not None and ym.shares_eop:
            tangible_eq = ym.common_equity - (ym.goodwill or 0.0) - (ym.intangibles or 0.0)
            ym.tangible_book_value_per_share = _safe_div(tangible_eq, ym.shares_eop)

        years.append(ym)

    # Wire up averages & growth using year-over-year context.
    fy_index = {ym.fiscal_year: ym for ym in years}
    # For averages we may need the year *before* the earliest selected year:
    extra_prev_equity = (
        _val_for_year(series["common_equity"], avg_anchor_fy) if avg_anchor_fy else None
    )
    if extra_prev_equity is None and avg_anchor_fy:
        tot_prev = _val_for_year(series["stockholders_equity"], avg_anchor_fy)
        pref_prev = _val_for_year(series["preferred_equity"], avg_anchor_fy)
        if tot_prev is not None and pref_prev is not None:
            extra_prev_equity = tot_prev - pref_prev
        else:
            extra_prev_equity = tot_prev
    extra_prev_assets = (
        _val_for_year(series["total_assets"], avg_anchor_fy) if avg_anchor_fy else None
    )
    extra_prev_eps_basic = None
    if avg_anchor_fy:
        prev_eps_pt = series["eps_basic"].by_fy().get(avg_anchor_fy)
        if prev_eps_pt:
            extra_prev_eps_basic = prev_eps_pt.val
        else:
            ni_prev = _val_for_year(series["net_income_to_common"], avg_anchor_fy) or _val_for_year(
                series["net_income"], avg_anchor_fy
            )
            shr_prev = _val_for_year(series["weighted_avg_shares_basic"], avg_anchor_fy)
            extra_prev_eps_basic = _safe_div(ni_prev, shr_prev)

    sorted_years_asc = sorted(years, key=lambda y: y.fiscal_year)
    for idx, ym in enumerate(sorted_years_asc):
        prev_ym = sorted_years_asc[idx - 1] if idx > 0 else None
        prev_eq = prev_ym.common_equity if prev_ym else extra_prev_equity
        prev_assets = prev_ym.total_assets if prev_ym else extra_prev_assets
        prev_eps = prev_ym.eps_basic if prev_ym else extra_prev_eps_basic

        avg_eq = _avg(ym.common_equity, prev_eq)
        avg_assets = _avg(ym.total_assets, prev_assets)
        ym.roe = _safe_div(ym.net_income_to_common or ym.net_income, avg_eq)
        ym.roa = _safe_div(ym.net_income, avg_assets)
        if ym.eps_basic is not None and prev_eps:
            ym.eps_growth = (ym.eps_basic / prev_eps) - 1.0

    # Assemble the result with most-recent-first ordering.
    years_desc = sorted(years, key=lambda y: y.fiscal_year, reverse=True)
    result = FundamentalsResult(ticker=ticker.upper(), years=years_desc, notes=notes)

    # TTM EPS: prefer summing the last 4 quarters of EarningsPerShareBasic
    # (companyfacts contains quarterly rows tagged Q1..Q3 + FY).
    result.ttm_eps = _ttm_eps(ext)
    if result.ttm_eps is None and result.latest:
        result.ttm_eps = result.latest.eps_basic
        notes.append("TTM EPS unavailable; using most recent annual EPS.")
    result.eps_12 = result.ttm_eps

    return result


def _ttm_eps(ext: XbrlFactExtractor) -> Optional[float]:
    """Compute trailing-twelve-month basic EPS from quarterly XBRL rows.

    Strategy: find the most recent reported period end across both annual
    and quarterly rows.

      * If the most recent end date is an FY row, return that value
        directly (the trailing 4 quarters by definition).
      * Otherwise, the most recent end date is in a fiscal year FY_n
        whose annual report has not yet been filed. Combine Q1..Q3 of
        FY_n with the (FY_{n-1} − Q1..Q3 of FY_{n-1}) remainder.

    Returns None if neither path can be satisfied.
    """
    eps_entry = ext.facts.get("EarningsPerShareBasic")
    if not eps_entry:
        return None

    rows: list[dict] = []
    for _unit, points in (eps_entry.get("units") or {}).items():
        rows.extend(points)
    if not rows:
        return None

    quarter_rows = [r for r in rows if r.get("fp") in ("Q1", "Q2", "Q3")]
    fy_rows = [r for r in rows if r.get("fp") == "FY"]
    quarter_rows.sort(key=lambda r: r.get("end", ""), reverse=True)
    fy_rows.sort(key=lambda r: r.get("end", ""), reverse=True)

    latest_fy_end = fy_rows[0].get("end", "") if fy_rows else ""
    latest_q_end = quarter_rows[0].get("end", "") if quarter_rows else ""

    # If the most recent annual data point is at least as recent as the latest
    # quarter, the FY value already represents the trailing 12 months.
    if latest_fy_end and latest_fy_end >= latest_q_end:
        return float(fy_rows[0]["val"])

    if not quarter_rows or not fy_rows:
        return None

    fy_n = quarter_rows[0].get("fy")
    if fy_n is None:
        return None

    qrows_fy_n = [r for r in quarter_rows if r.get("fy") == fy_n]
    if not qrows_fy_n:
        return None
    seen_fp = {}
    for r in qrows_fy_n:
        fp = r.get("fp")
        if fp not in seen_fp:
            seen_fp[fp] = r
    sum_q_fy_n = sum(float(r["val"]) for r in seen_fp.values())

    fy_prev = fy_n - 1
    fy_prev_row = next((r for r in fy_rows if r.get("fy") == fy_prev), None)
    qrows_fy_prev = [r for r in quarter_rows if r.get("fy") == fy_prev]
    if not fy_prev_row or not qrows_fy_prev:
        return None
    seen_fp_prev = {}
    for r in qrows_fy_prev:
        fp = r.get("fp")
        if fp not in seen_fp_prev:
            seen_fp_prev[fp] = r
    sum_q_fy_prev = sum(float(r["val"]) for r in seen_fp_prev.values())
    remainder = float(fy_prev_row["val"]) - sum_q_fy_prev
    return sum_q_fy_n + remainder
