"""Excel and PDF report exporters."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import LETTER
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import (
    Image,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from ..calculations.fundamentals import FundamentalsResult
from ..calculations.technicals import TechnicalsResult


def _years_dataframe(fund: FundamentalsResult) -> pd.DataFrame:
    rows = []
    for y in fund.years:
        rows.append(
            {
                "fiscal_year": y.fiscal_year,
                "period_end": y.period_end,
                "net_income": y.net_income,
                "net_income_to_common": y.net_income_to_common,
                "common_equity": y.common_equity,
                "preferred_equity": y.preferred_equity,
                "total_assets": y.total_assets,
                "goodwill": y.goodwill,
                "intangibles": y.intangibles,
                "shares_eop": y.shares_eop,
                "eps_basic": y.eps_basic,
                "eps_diluted": y.eps_diluted,
                "eps_growth": y.eps_growth,
                "book_value_per_share": y.book_value_per_share,
                "tangible_book_value_per_share": y.tangible_book_value_per_share,
                "roe": y.roe,
                "roa": y.roa,
                "dividends_per_share": y.dividends_per_share,
            }
        )
    return pd.DataFrame(rows)


def export_excel(
    out_path: Path,
    *,
    company_name: str,
    ticker: str,
    fundamentals: FundamentalsResult,
    technicals: TechnicalsResult,
    yahoo_info: Optional[dict] = None,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with pd.ExcelWriter(out_path, engine="openpyxl") as writer:
        meta = pd.DataFrame(
            [
                ("Ticker", ticker),
                ("Company", company_name),
                ("Generated", datetime.utcnow().isoformat(timespec="seconds") + "Z"),
                ("Last close", technicals.last_close),
                ("52w high", technicals.high_52w),
                ("52w low", technicals.low_52w),
                ("TTM EPS", fundamentals.ttm_eps),
                ("EPS 12", fundamentals.eps_12),
            ],
            columns=["field", "value"],
        )
        meta.to_excel(writer, sheet_name="overview", index=False)
        _years_dataframe(fundamentals).to_excel(writer, sheet_name="fundamentals", index=False)
        if technicals.history is not None and not technicals.history.empty:
            technicals.history.tail(252 * 5).to_excel(writer, sheet_name="prices")
        if yahoo_info:
            yi_rows = [(k, v) for k, v in yahoo_info.items() if not isinstance(v, (list, dict))]
            pd.DataFrame(yi_rows, columns=["field", "value"]).to_excel(
                writer, sheet_name="yahoo_info", index=False
            )
        if fundamentals.notes:
            pd.DataFrame({"note": fundamentals.notes}).to_excel(
                writer, sheet_name="notes", index=False
            )
    return out_path


def export_pdf(
    out_path: Path,
    *,
    company_name: str,
    ticker: str,
    fundamentals: FundamentalsResult,
    technicals: TechnicalsResult,
    chart_png: Optional[Path] = None,
    yahoo_info: Optional[dict] = None,
) -> Path:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    doc = SimpleDocTemplate(
        str(out_path),
        pagesize=LETTER,
        leftMargin=0.6 * inch,
        rightMargin=0.6 * inch,
        topMargin=0.6 * inch,
        bottomMargin=0.6 * inch,
    )

    story = []
    story.append(Paragraph(f"<b>{ticker}</b> — {company_name}", styles["Title"]))
    story.append(Paragraph(
        f"Generated {datetime.utcnow().isoformat(timespec='seconds')}Z",
        styles["Italic"],
    ))
    story.append(Spacer(1, 12))

    # Snapshot
    last_close = technicals.last_close
    snap_rows = [
        ["Last close", f"${last_close:,.2f}" if last_close else "—"],
        ["52w high", f"${technicals.high_52w:,.2f}" if technicals.high_52w else "—"],
        ["52w low", f"${technicals.low_52w:,.2f}" if technicals.low_52w else "—"],
    ]
    for window, val in technicals.ma_values.items():
        snap_rows.append([f"MA{window}", f"${val:,.2f}" if val else "—"])
    if yahoo_info:
        mc = yahoo_info.get("marketCap")
        if mc:
            snap_rows.append(["Market cap", f"${mc / 1e9:,.2f}B"])
        dy = yahoo_info.get("dividendYield")
        if dy is not None:
            snap_rows.append(["Dividend yield", f"{dy * 100:,.2f}%"])
    snap_tbl = Table(snap_rows, hAlign="LEFT", colWidths=[2.0 * inch, 1.5 * inch])
    snap_tbl.setStyle(
        TableStyle([
            ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
            ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
            ("FONT", (0, 0), (-1, -1), "Helvetica", 9),
        ])
    )
    story.append(Paragraph("<b>Price Summary</b>", styles["Heading2"]))
    story.append(snap_tbl)
    story.append(Spacer(1, 12))

    # Fundamentals
    df = _years_dataframe(fundamentals)
    if not df.empty:
        header = ["Metric"] + [f"FY{y}" for y in df["fiscal_year"]]

        def _row(label: str, key: str, formatter):
            return [label] + [formatter(v) for v in df[key].tolist()]

        def _money(v):
            if v is None or pd.isna(v):
                return "—"
            if abs(v) >= 1e9:
                return f"${v / 1e9:,.2f}B"
            if abs(v) >= 1e6:
                return f"${v / 1e6:,.2f}M"
            return f"${v:,.0f}"

        def _ps(v):
            return f"${v:,.2f}" if v is not None and not pd.isna(v) else "—"

        def _pct(v):
            return f"{v * 100:,.2f}%" if v is not None and not pd.isna(v) else "—"

        def _num(v):
            return f"{v:,.0f}" if v is not None and not pd.isna(v) else "—"

        rows = [
            header,
            _row("Net income", "net_income", _money),
            _row("NI to common", "net_income_to_common", _money),
            _row("Total assets", "total_assets", _money),
            _row("Common equity", "common_equity", _money),
            _row("Shares EoP", "shares_eop", _num),
            _row("EPS basic", "eps_basic", _ps),
            _row("EPS growth", "eps_growth", _pct),
            _row("Book value / sh", "book_value_per_share", _ps),
            _row("Tangible BV / sh", "tangible_book_value_per_share", _ps),
            _row("ROE", "roe", _pct),
            _row("ROA", "roa", _pct),
        ]
        fund_tbl = Table(rows, hAlign="LEFT")
        fund_tbl.setStyle(
            TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
                ("FONT", (0, 0), (-1, -1), "Helvetica", 8),
                ("BOX", (0, 0), (-1, -1), 0.5, colors.grey),
                ("INNERGRID", (0, 0), (-1, -1), 0.25, colors.lightgrey),
                ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
            ])
        )
        story.append(Paragraph("<b>Fundamentals</b>", styles["Heading2"]))
        story.append(fund_tbl)
        story.append(Spacer(1, 12))

    if chart_png and Path(chart_png).exists():
        story.append(Paragraph("<b>Price Chart</b>", styles["Heading2"]))
        story.append(Image(str(chart_png), width=6.8 * inch, height=4.0 * inch))

    if fundamentals.notes:
        story.append(Spacer(1, 12))
        story.append(Paragraph("<b>Assumptions / Notes</b>", styles["Heading2"]))
        for n in fundamentals.notes:
            story.append(Paragraph(f"• {n}", styles["BodyText"]))

    doc.build(story)
    return out_path
