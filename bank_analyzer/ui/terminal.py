"""Rich-based terminal rendering of analyzer output."""
from __future__ import annotations

from typing import Optional

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from ..calculations.fundamentals import FundamentalsResult, YearMetrics
from ..calculations.technicals import TechnicalsResult


def _fmt_money(v: Optional[float]) -> str:
    if v is None:
        return "—"
    if abs(v) >= 1e9:
        return f"${v / 1e9:,.2f}B"
    if abs(v) >= 1e6:
        return f"${v / 1e6:,.2f}M"
    return f"${v:,.0f}"


def _fmt_per_share(v: Optional[float]) -> str:
    return f"${v:,.2f}" if v is not None else "—"


def _fmt_pct(v: Optional[float]) -> str:
    return f"{v * 100:,.2f}%" if v is not None else "—"


def _fmt_num(v: Optional[float]) -> str:
    return f"{v:,.0f}" if v is not None else "—"


def render_summary(
    *,
    company_name: str,
    ticker: str,
    fundamentals: FundamentalsResult,
    technicals: TechnicalsResult,
    yahoo_info: Optional[dict] = None,
    seeking_alpha_link: Optional[str] = None,
    sa_headlines: Optional[list] = None,
    extras: Optional[dict] = None,
    console: Optional[Console] = None,
) -> None:
    """Pretty-print the analysis summary to the terminal."""
    console = console or Console()
    extras = extras or {}

    header = Panel.fit(
        f"[bold cyan]{ticker}[/bold cyan] — {company_name}",
        subtitle=f"Last close {_fmt_per_share(technicals.last_close)}",
    )
    console.print(header)

    # ----- Price summary --------------------------------------------------
    price_tbl = Table(title="Price Summary", show_header=True, header_style="bold")
    price_tbl.add_column("Metric")
    price_tbl.add_column("Value", justify="right")
    price_tbl.add_row("Last close", _fmt_per_share(technicals.last_close))
    price_tbl.add_row("52-week high", _fmt_per_share(technicals.high_52w))
    price_tbl.add_row("52-week low", _fmt_per_share(technicals.low_52w))
    for window, val in technicals.ma_values.items():
        price_tbl.add_row(f"MA{window}", _fmt_per_share(val))
    if yahoo_info:
        price_tbl.add_row("Market cap", _fmt_money(yahoo_info.get("marketCap")))
        price_tbl.add_row("Beta", f"{yahoo_info.get('beta'):.2f}" if yahoo_info.get("beta") is not None else "—")
        dy = yahoo_info.get("dividendYield")
        price_tbl.add_row("Dividend yield", _fmt_pct(dy) if dy is not None else "—")
    console.print(price_tbl)

    # ----- Fundamentals --------------------------------------------------
    fund_tbl = Table(title="Fundamentals (last 3 fiscal years)", show_header=True, header_style="bold")
    fund_tbl.add_column("Metric")
    for ym in fundamentals.years:
        fund_tbl.add_column(f"FY{ym.fiscal_year}", justify="right")

    rows: list[tuple[str, callable]] = [
        ("Net income", lambda y: _fmt_money(y.net_income)),
        ("NI to common", lambda y: _fmt_money(y.net_income_to_common)),
        ("Total assets", lambda y: _fmt_money(y.total_assets)),
        ("Common equity", lambda y: _fmt_money(y.common_equity)),
        ("Goodwill", lambda y: _fmt_money(y.goodwill)),
        ("Other intangibles", lambda y: _fmt_money(y.intangibles)),
        ("Shares outstanding (EoP)", lambda y: _fmt_num(y.shares_eop)),
        ("EPS basic", lambda y: _fmt_per_share(y.eps_basic)),
        ("EPS diluted", lambda y: _fmt_per_share(y.eps_diluted)),
        ("EPS growth (YoY)", lambda y: _fmt_pct(y.eps_growth)),
        ("Book value / share", lambda y: _fmt_per_share(y.book_value_per_share)),
        ("Tangible BV / share", lambda y: _fmt_per_share(y.tangible_book_value_per_share)),
        ("ROE", lambda y: _fmt_pct(y.roe)),
        ("ROA", lambda y: _fmt_pct(y.roa)),
        ("DPS (declared)", lambda y: _fmt_per_share(y.dividends_per_share)),
    ]
    for label, fn in rows:
        fund_tbl.add_row(label, *[fn(y) for y in fundamentals.years])

    console.print(fund_tbl)

    # ----- TTM / Bonus row -----------------------------------------------
    ttm_tbl = Table(title="Trailing & Valuation", show_header=True, header_style="bold")
    ttm_tbl.add_column("Metric")
    ttm_tbl.add_column("Value", justify="right")
    ttm_tbl.add_row("TTM EPS", _fmt_per_share(fundamentals.ttm_eps))
    ttm_tbl.add_row("EPS 12 (alias)", _fmt_per_share(fundamentals.eps_12))
    if technicals.last_close and fundamentals.ttm_eps:
        pe = technicals.last_close / fundamentals.ttm_eps if fundamentals.ttm_eps else None
        ttm_tbl.add_row("P/E (TTM)", f"{pe:,.2f}" if pe else "—")
    latest = fundamentals.latest
    if latest and latest.tangible_book_value_per_share and technicals.last_close:
        p_tbv = technicals.last_close / latest.tangible_book_value_per_share
        ttm_tbl.add_row("P/TBV", f"{p_tbv:,.2f}")
    if latest and latest.book_value_per_share and technicals.last_close:
        p_b = technicals.last_close / latest.book_value_per_share
        ttm_tbl.add_row("P/B", f"{p_b:,.2f}")

    cet1 = extras.get("cet1_ratio")
    if cet1 is not None:
        ttm_tbl.add_row("CET1 ratio (filing scrape)", f"{cet1:.2f}%")
    console.print(ttm_tbl)

    # ----- Notes & links -------------------------------------------------
    if fundamentals.notes:
        console.print(Panel("\n".join(f"• {n}" for n in fundamentals.notes), title="Assumptions / Notes", border_style="yellow"))

    if seeking_alpha_link:
        console.print(f"[dim]Seeking Alpha:[/dim] {seeking_alpha_link}")

    if sa_headlines:
        h_tbl = Table(title="Recent Seeking Alpha headlines (public RSS)", header_style="bold")
        h_tbl.add_column("Date")
        h_tbl.add_column("Title")
        for h in sa_headlines[:5]:
            h_tbl.add_row(h.published[:16] if h.published else "—", h.title)
        console.print(h_tbl)
