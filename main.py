"""CLI entry point for the bank stock analyzer."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from rich.console import Console

from bank_analyzer.analyzer import Analyzer
from bank_analyzer.charts.candlestick import save_candlestick_png
from bank_analyzer.config import load_config
from bank_analyzer.ui.reports import export_excel, export_pdf
from bank_analyzer.ui.terminal import render_summary

console = Console()


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Bank stock analyzer (SEC EDGAR + Yahoo Finance)."
    )
    p.add_argument("ticker", nargs="?", help="Ticker symbol (e.g. JPM, BAC, WFC, C)")
    p.add_argument("--peers", nargs="*", default=[], help="Peer tickers for comparison")
    p.add_argument("--no-chart", action="store_true", help="Skip PNG chart generation")
    p.add_argument("--excel", action="store_true", help="Also export an Excel workbook")
    p.add_argument("--pdf", action="store_true", help="Also export a PDF report")
    p.add_argument("--config", help="Optional path to config.yaml", default=None)
    return p.parse_args()


def prompt_for_ticker() -> str:
    return console.input("[bold]Ticker symbol[/bold] (e.g. JPM, BAC, WFC, C): ").strip()


def main() -> int:
    args = parse_args()
    cfg = load_config(args.config)

    ticker = (args.ticker or prompt_for_ticker()).upper()
    if not ticker:
        console.print("[red]No ticker provided.[/red]")
        return 2

    analyzer = Analyzer(config=cfg)
    try:
        ok, reason = analyzer.validate_ticker(ticker)
        if not ok:
            console.print(f"[red]Ticker {ticker!r} failed validation:[/red] {reason}")
            return 2

        result = analyzer.analyze(ticker)

        chart_path: Path | None = None
        if not args.no_chart and not result.technicals.history.empty:
            chart_path = cfg.output_dir / f"{ticker}_candles.png"
            try:
                save_candlestick_png(
                    result.technicals.history,
                    chart_path,
                    title=f"{ticker} — {result.company_name}",
                    moving_averages=cfg.moving_averages,
                )
            except Exception as exc:  # noqa: BLE001
                console.print(f"[yellow]Chart generation failed: {exc}[/yellow]")
                chart_path = None

        render_summary(
            company_name=result.company_name,
            ticker=result.ticker,
            fundamentals=result.fundamentals,
            technicals=result.technicals,
            yahoo_info=result.yahoo_info,
            seeking_alpha_link=result.seeking_alpha_link,
            sa_headlines=result.seeking_alpha_headlines,
            extras=result.extras,
            console=console,
        )

        if chart_path:
            console.print(f"[green]Chart written:[/green] {chart_path}")

        if args.excel:
            xlsx = cfg.output_dir / f"{ticker}_report.xlsx"
            export_excel(
                xlsx,
                company_name=result.company_name,
                ticker=result.ticker,
                fundamentals=result.fundamentals,
                technicals=result.technicals,
                yahoo_info=result.yahoo_info,
            )
            console.print(f"[green]Excel report written:[/green] {xlsx}")

        if args.pdf:
            pdf = cfg.output_dir / f"{ticker}_report.pdf"
            export_pdf(
                pdf,
                company_name=result.company_name,
                ticker=result.ticker,
                fundamentals=result.fundamentals,
                technicals=result.technicals,
                chart_png=chart_path,
                yahoo_info=result.yahoo_info,
            )
            console.print(f"[green]PDF report written:[/green] {pdf}")

        if args.peers:
            console.rule("Peer comparison")
            peers_results = analyzer.compare_peers(ticker, args.peers)
            for t, r in peers_results.items():
                latest = r.fundamentals.latest
                last_close = r.technicals.last_close or 0.0
                ttm = r.fundamentals.ttm_eps
                ttm_s = f"${ttm:,.2f}" if ttm is not None else "—"
                if latest and latest.tangible_book_value_per_share and last_close:
                    p_tbv = last_close / latest.tangible_book_value_per_share
                    p_tbv_s = f"{p_tbv:,.2f}"
                else:
                    p_tbv_s = "—"
                console.print(
                    f"[bold]{t}[/bold]  "
                    f"close=${last_close:,.2f}  "
                    f"TTM EPS={ttm_s}  "
                    f"P/TBV={p_tbv_s}"
                )

        return 0
    finally:
        analyzer.close()


if __name__ == "__main__":
    sys.exit(main())
