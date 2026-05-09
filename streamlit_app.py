"""Streamlit dashboard — bank stock SCREENER with single-stock drill-down.

Run with:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import os

# Headless matplotlib backend — required on Streamlit Cloud (no display server).
os.environ.setdefault("MPLBACKEND", "Agg")
import matplotlib
matplotlib.use("Agg")

import numpy as np
import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

# Bridge Streamlit Cloud "Secrets" → environment variables BEFORE the analyzer
# imports load_config (which reads SEC_USER_AGENT from os.environ).
try:
    for _k, _v in st.secrets.items():  # type: ignore[attr-defined]
        if isinstance(_v, str) and _k not in os.environ:
            os.environ[_k] = _v
except Exception:  # noqa: BLE001
    pass

from bank_analyzer.analyzer import Analyzer  # noqa: E402
from bank_analyzer.charts.plotly_charts import build_plotly_chart  # noqa: E402
from bank_analyzer.charts.tradingview_widget import (  # noqa: E402
    advanced_chart_html,
    mini_chart_html,
)
from bank_analyzer.config import load_config  # noqa: E402
from bank_analyzer.screener import run_screener  # noqa: E402
from bank_analyzer.universe import SEGMENTS, UNIVERSE, all_tickers, segment_of  # noqa: E402

# --------------------------------------------------------------------------- page
st.set_page_config(
    page_title="Bank Stock Screener",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

st.markdown(
    """
    <style>
      .stMetric { background: #f8fafc; border: 1px solid #e2e8f0;
                  border-radius: 10px; padding: 12px 14px; }
      .stMetric label { color: #475569 !important; font-weight: 500 !important; }
      .stMetric [data-testid="stMetricValue"] { font-size: 1.45rem !important; }
      .stTabs [data-baseweb="tab-list"] { gap: 6px; }
      .stTabs [data-baseweb="tab"] { padding: 10px 14px; }
      .small-caption { color: #64748b; font-size: 12px; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- session
if "view" not in st.session_state:
    st.session_state.view = "screener"
if "drill_ticker" not in st.session_state:
    st.session_state.drill_ticker = None


@st.cache_resource(show_spinner=False)
def get_analyzer() -> Analyzer:
    return Analyzer(load_config())


@st.cache_data(show_spinner=False, ttl=60 * 60)
def cached_analyze(ticker: str):
    return get_analyzer().analyze(ticker)


@st.cache_data(show_spinner=False, ttl=60 * 60)
def cached_screen(tickers: tuple[str, ...]):
    """Cached screener run. Tuple key is hashable for st.cache_data."""
    progress_box = st.empty()
    bar = progress_box.progress(0, text="Pulling SEC + Yahoo data...")

    def _on_progress(done: int, total: int, current: str):
        bar.progress(done / total, text=f"Loaded {done}/{total} — last: {current}")

    df = run_screener(
        analyzer=get_analyzer(),
        tickers=list(tickers),
        segment_lookup=segment_of,
        max_workers=6,
        progress=_on_progress,
    )
    progress_box.empty()
    return df


# --------------------------------------------------------------------------- sidebar
chosen_segments: list[str] = list(SEGMENTS)

with st.sidebar:
    st.title("🏦 Bank Screener")
    st.caption("US bank stocks · SEC EDGAR fundamentals · Yahoo prices · TradingView")

    nav = st.radio(
        "View",
        options=["🔎 Screener", "📊 Stock detail"],
        index=0 if st.session_state.view == "screener" else 1,
        label_visibility="collapsed",
    )
    st.session_state.view = "screener" if nav.startswith("🔎") else "detail"

    st.divider()

    if st.session_state.view == "screener":
        st.markdown("### Universe filter")
        chosen_segments = st.multiselect(
            "Segments",
            options=SEGMENTS,
            default=["Nano-Cap Community"],
            help=(
                "Default = Nano-Cap Community (typically <$200M market cap, "
                "many <$100M). Add 'Small Community' or other segments to widen."
            ),
        )

        st.markdown("### Refresh")
        if st.button("🔄 Re-run screener", use_container_width=True):
            cached_screen.clear()
            st.rerun()
    else:
        st.markdown("### Pick a ticker")
        manual = st.text_input(
            "Ticker", value=(st.session_state.drill_ticker or "JPM"), placeholder="e.g. JPM"
        ).strip().upper()
        if st.button("Analyze →", type="primary", use_container_width=True):
            st.session_state.drill_ticker = manual
            st.rerun()

        st.markdown("**Quick-pick**")
        chips = ["JPM", "BAC", "WFC", "C", "USB", "PNC", "TFC", "BK", "GS", "MS"]
        ncols = 5
        for r in range(0, len(chips), ncols):
            cols = st.columns(ncols)
            for c, t in zip(cols, chips[r : r + ncols]):
                if c.button(t, key=f"chip_{t}", use_container_width=True):
                    st.session_state.drill_ticker = t
                    st.rerun()

    chart_theme = st.selectbox("Chart theme", ["light", "dark"], index=0)

    st.divider()
    st.caption(
        "Data: SEC EDGAR XBRL · Yahoo Finance · TradingView. "
        "First run is slow (cold cache); subsequent runs are fast."
    )


# ============================================================================
#                                   SCREENER
# ============================================================================
def render_screener(chosen_segments: list[str], chart_theme: str) -> None:
    st.markdown("## 🔎 US Bank Stock Screener")
    st.caption(
        "Filter ~35 publicly-traded US banks by valuation, profitability, "
        "capital strength, and momentum. Click any row for the deep-dive view."
    )

    # Pull the data (cached).
    universe_tickers = tuple(
        b.ticker for b in UNIVERSE if b.segment in chosen_segments
    )
    if not universe_tickers:
        st.warning("Pick at least one segment in the sidebar.")
        return

    df = cached_screen(universe_tickers)
    if df is None or df.empty:
        st.error(
            "No screener data could be loaded. Yahoo Finance may be temporarily "
            "unavailable for cloud IPs — try again in a few minutes."
        )
        return

    # ----- summary tiles ----------------------------------------------------
    total = len(df)
    pos_eps = (df["eps_growth_yoy"] > 0).sum() if "eps_growth_yoy" in df else 0
    above_ma200 = df["above_ma200"].sum() if "above_ma200" in df else 0
    median_pe = df["pe_ttm"].median()
    median_ptbv = df["p_tbv"].median()

    t1, t2, t3, t4, t5 = st.columns(5)
    t1.metric("Banks", f"{total}")
    t2.metric("Positive EPS YoY", f"{int(pos_eps)} / {total}")
    t3.metric("Trading > MA200", f"{int(above_ma200)} / {total}")
    t4.metric("Median P/E (TTM)", f"{median_pe:.1f}" if pd.notna(median_pe) else "—")
    t5.metric("Median P/TBV", f"{median_ptbv:.2f}" if pd.notna(median_ptbv) else "—")

    st.divider()

    # ----- filter controls --------------------------------------------------
    st.markdown("### Filters")
    st.caption(
        "Defaults are pre-set to community-bank quality screen: "
        "**market cap < $150M · ROE ≥ 12% · ROA ≥ 0.9%**. "
        "Adjust the sliders to widen or tighten the screen."
    )
    fcols = st.columns(4)

    with fcols[0]:
        mc_max_universe = float(df["market_cap"].max(skipna=True) or 0) / 1e6
        mc_max_slider = max(mc_max_universe, 5000.0)
        mc_max = st.slider(
            "Max market cap (USD millions)",
            min_value=0.0,
            max_value=mc_max_slider,
            value=150.0,                 # ← user requirement
            step=10.0,
            help="Default 150 = under $150M (true community / micro-cap range).",
        )
    with fcols[1]:
        roe_min = st.slider(
            "Min ROE (%)",
            min_value=-20.0,
            max_value=40.0,
            value=12.0,                  # ← user requirement
            step=0.5,
        )
    with fcols[2]:
        roa_min = st.slider(
            "Min ROA (%)",
            min_value=-2.0,
            max_value=5.0,
            value=0.9,                   # ← user requirement
            step=0.1,
        )
    with fcols[3]:
        dy_min = st.slider(
            "Min dividend yield (%)",
            min_value=0.0,
            max_value=10.0,
            value=0.0,
            step=0.1,
        )

    fcols2 = st.columns(4)
    with fcols2[0]:
        ptbv_max = st.slider(
            "Max P/TBV",
            min_value=0.0,
            max_value=10.0,
            value=10.0,
            step=0.1,
        )
    with fcols2[1]:
        require_pos_eps = st.checkbox("EPS growth YoY > 0", value=False)
    with fcols2[2]:
        sort_by = st.selectbox(
            "Sort by",
            options=[
                "roe",
                "roa",
                "market_cap",
                "p_tbv",
                "pe_ttm",
                "eps_growth_yoy",
                "dividend_yield",
                "pct_off_high_52w",
            ],
            index=0,
        )
    with fcols2[3]:
        sort_dir = st.selectbox("Sort direction", options=["desc", "asc"], index=0)

    # Apply filters --------------------------------------------------------
    f = df.copy()
    # Market cap filter: rows missing market cap are excluded (we can't verify).
    f = f[f["market_cap"].notna() & (f["market_cap"] / 1e6 <= mc_max)]
    if roe_min > -20:
        f = f[f["roe"].fillna(-1) >= roe_min / 100]
    if roa_min > -2:
        f = f[f["roa"].fillna(-1) >= roa_min / 100]
    if dy_min > 0:
        f = f[f["dividend_yield"].fillna(0) >= dy_min / 100]
    if ptbv_max < 10:
        f = f[f["p_tbv"].isna() | (f["p_tbv"] <= ptbv_max)]
    if require_pos_eps:
        f = f[f["eps_growth_yoy"].fillna(-1) > 0]

    f = f.sort_values(sort_by, ascending=(sort_dir == "asc"), na_position="last").reset_index(drop=True)

    if len(f) == 0:
        st.warning(
            "No banks match your current filters. Try loosening: "
            "raise the max market cap, lower the min ROE/ROA, or pick more segments."
        )
    else:
        st.markdown(f"### Results — **{len(f)}** of {total} banks match")

    # ----- main table (PRIMARY UI) -----------------------------------------
    # Show market cap in millions for readability with community banks.
    f_view = f.copy()
    if "market_cap" in f_view.columns:
        f_view["market_cap_m"] = f_view["market_cap"] / 1e6

    display_cols = {
        "ticker": "Ticker",
        "company_name": "Company",
        "segment": "Segment",
        "market_cap_m": "Mkt cap ($M)",
        "last_close": "Price",
        "roe": "ROE",
        "roa": "ROA",
        "p_tbv": "P/TBV",
        "pb": "P/B",
        "pe_ttm": "P/E (TTM)",
        "eps_growth_yoy": "EPS YoY",
        "dividend_yield": "Div yield",
        "ttm_eps": "TTM EPS",
        "tbv_per_share": "TBV/sh",
        "pct_off_high_52w": "% off 52w high",
        "above_ma200": "> MA200",
    }
    keep = [c for c in display_cols if c in f_view.columns]
    f_disp = f_view[keep].rename(columns={c: display_cols[c] for c in keep})

    st.dataframe(
        f_disp,
        use_container_width=True,
        hide_index=True,
        height=min(900, 60 + 36 * max(len(f_disp), 1)),
        column_config={
            "Mkt cap ($M)": st.column_config.NumberColumn(format="$%.1fM"),
            "Price": st.column_config.NumberColumn(format="$%.2f"),
            "P/E (TTM)": st.column_config.NumberColumn(format="%.1f"),
            "P/B": st.column_config.NumberColumn(format="%.2f"),
            "P/TBV": st.column_config.NumberColumn(format="%.2f"),
            "ROE": st.column_config.NumberColumn(format="%.2f%%"),
            "ROA": st.column_config.NumberColumn(format="%.2f%%"),
            "EPS YoY": st.column_config.NumberColumn(format="%.2f%%"),
            "Div yield": st.column_config.NumberColumn(format="%.2f%%"),
            "TTM EPS": st.column_config.NumberColumn(format="$%.2f"),
            "TBV/sh": st.column_config.NumberColumn(format="$%.2f"),
            "% off 52w high": st.column_config.NumberColumn(format="%.1f%%"),
            "> MA200": st.column_config.CheckboxColumn(),
        },
    )

    # CSV download for the matched rows
    st.download_button(
        "⬇ Download matched banks as CSV",
        data=f_disp.to_csv(index=False).encode("utf-8"),
        file_name="matched_banks.csv",
        mime="text/csv",
        use_container_width=False,
    )

    # Drill-down picker
    st.markdown("### Drill into a stock")
    pick_cols = st.columns([3, 1])
    with pick_cols[0]:
        pick = st.selectbox(
            "Select ticker for the detail view",
            options=f["ticker"].tolist(),
            label_visibility="collapsed",
        )
    with pick_cols[1]:
        if st.button("Open detail →", type="primary", use_container_width=True):
            st.session_state.drill_ticker = pick
            st.session_state.view = "detail"
            st.rerun()

    st.divider()

    # ----- visualization (collapsed by default — table is the primary UI) -----
    with st.expander("📊 Charts (scatter, bar, mini-charts)", expanded=False):
        vt1, vt2, vt3 = st.tabs(["🟦 Scatter: ROE vs P/TBV", "📊 Bar charts", "🖼 Mini charts"])

    with vt1:
        st.caption(
            "ROE on x-axis vs P/TBV on y-axis. Banks in the lower-right corner "
            "(high ROE, low P/TBV) are the cheap-and-profitable quadrant."
        )
        scatter_df = f.dropna(subset=["roe", "p_tbv"])
        if not scatter_df.empty:
            import plotly.express as px

            fig = px.scatter(
                scatter_df,
                x="roe",
                y="p_tbv",
                size=scatter_df["market_cap"].fillna(0).clip(lower=1),
                color="segment",
                hover_name="ticker",
                hover_data={"company_name": True, "roe": ":.2%", "p_tbv": ":.2f", "market_cap": ":,.0f"},
                labels={"roe": "ROE", "p_tbv": "P/TBV"},
                size_max=40,
            )
            fig.update_layout(
                template=("plotly_dark" if chart_theme == "dark" else "plotly_white"),
                height=500,
                margin=dict(l=20, r=20, t=10, b=20),
            )
            fig.update_xaxes(tickformat=".1%")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Not enough data points to plot.")

    with vt2:
        st.caption("Sortable bar charts for quick visual ranking.")
        metric_for_bar = st.selectbox(
            "Bar metric",
            options=["roe", "roa", "p_tbv", "pe_ttm", "dividend_yield", "eps_growth_yoy"],
            index=0,
        )
        bar_df = f.dropna(subset=[metric_for_bar]).sort_values(metric_for_bar, ascending=False).head(20)
        import plotly.express as px

        fig = px.bar(
            bar_df,
            x="ticker",
            y=metric_for_bar,
            color="segment",
            hover_data={"company_name": True},
        )
        fig.update_layout(
            template=("plotly_dark" if chart_theme == "dark" else "plotly_white"),
            height=420,
            margin=dict(l=20, r=20, t=10, b=20),
            xaxis_title="",
            yaxis_title=metric_for_bar,
        )
        if metric_for_bar in ("roe", "roa", "dividend_yield", "eps_growth_yoy"):
            fig.update_yaxes(tickformat=".1%")
        st.plotly_chart(fig, use_container_width=True)

    with vt3:
        st.caption("12-month TradingView mini-charts for the top filtered banks.")
        topn = f.head(8)
        mc_cols = st.columns(4)
        for i, (_, row) in enumerate(topn.iterrows()):
            with mc_cols[i % 4]:
                st.markdown(f"**{row['ticker']}** — {row['company_name'][:24]}")
                components.html(
                    mini_chart_html(row["ticker"], theme=chart_theme, height=200),
                    height=210,
                    scrolling=False,
                )


# ============================================================================
#                                  STOCK DETAIL
# ============================================================================
def render_detail(ticker: str, chart_theme: str) -> None:
    if not ticker:
        st.info("Pick a ticker from the screener or the sidebar.")
        return

    try:
        result = cached_analyze(ticker)
    except Exception as exc:  # noqa: BLE001
        st.error(f"Could not load `{ticker}`: {exc}")
        return

    fund = result.fundamentals
    tech = result.technicals
    latest = fund.latest

    left, right = st.columns([3, 1])
    with left:
        st.markdown(f"## {result.ticker} — {result.company_name}")
        st.caption(f"Currently showing **{result.ticker}**. Use the sidebar to switch.")
    with right:
        st.markdown(f"[SEC filings]({result.sec.info.edgar_url})")
        if result.yahoo_info.get("website"):
            st.markdown(f"[Company site]({result.yahoo_info['website']})")
        if st.button("← Back to screener", use_container_width=True):
            st.session_state.view = "screener"
            st.rerun()

    # Big metric tiles
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Last close", f"${tech.last_close:,.2f}" if tech.last_close else "—")
    m2.metric("TTM EPS", f"${fund.ttm_eps:,.2f}" if fund.ttm_eps else "—")
    m3.metric(
        "P/E (TTM)",
        f"{tech.last_close / fund.ttm_eps:,.2f}" if (tech.last_close and fund.ttm_eps) else "—",
    )
    m4.metric(
        "P/TBV",
        f"{tech.last_close / latest.tangible_book_value_per_share:,.2f}"
        if (latest and latest.tangible_book_value_per_share and tech.last_close)
        else "—",
    )
    dy = result.yahoo_info.get("dividendYield")
    m5.metric("Dividend yield", f"{dy * 100:,.2f}%" if dy else "—")

    m6, m7, m8, m9, m10 = st.columns(5)
    m6.metric("52-week high", f"${tech.high_52w:,.2f}" if tech.high_52w else "—")
    m7.metric("52-week low", f"${tech.low_52w:,.2f}" if tech.low_52w else "—")
    m8.metric("MA50", f"${tech.ma_values.get(50):,.2f}" if tech.ma_values.get(50) else "—")
    m9.metric("MA200", f"${tech.ma_values.get(200):,.2f}" if tech.ma_values.get(200) else "—")
    mc = result.yahoo_info.get("marketCap")
    m10.metric("Market cap", f"${mc / 1e9:,.1f}B" if mc else "—")

    st.divider()

    tabs = st.tabs(["📊 TradingView", "📈 5y history", "💰 Fundamentals", "📰 News"])
    with tabs[0]:
        components.html(
            advanced_chart_html(result.ticker, theme=chart_theme, height=620),
            height=640,
        )
    with tabs[1]:
        plotly_template = "plotly_dark" if chart_theme == "dark" else "plotly_white"
        fig = build_plotly_chart(
            tech.history,
            title=f"{result.ticker} — {result.company_name} (5y)",
            moving_averages=(20, 50, 200, 252),
        )
        fig.update_layout(template=plotly_template)
        st.plotly_chart(fig, use_container_width=True)
    with tabs[2]:
        rows = []
        for y in fund.years:
            rows.append({
                "Fiscal year": f"FY{y.fiscal_year}",
                "Period end": y.period_end,
                "Net income": y.net_income,
                "Total assets": y.total_assets,
                "Common equity": y.common_equity,
                "Shares (EoP)": y.shares_eop,
                "EPS basic": y.eps_basic,
                "EPS growth": y.eps_growth,
                "BV/share": y.book_value_per_share,
                "TBV/share": y.tangible_book_value_per_share,
                "ROE": y.roe,
                "ROA": y.roa,
                "DPS": y.dividends_per_share,
            })
        if rows:
            st.dataframe(
                rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Net income": st.column_config.NumberColumn(format="$%.0f"),
                    "Total assets": st.column_config.NumberColumn(format="$%.0f"),
                    "Common equity": st.column_config.NumberColumn(format="$%.0f"),
                    "Shares (EoP)": st.column_config.NumberColumn(format="%.0f"),
                    "EPS basic": st.column_config.NumberColumn(format="$%.2f"),
                    "EPS growth": st.column_config.NumberColumn(format="%.2f%%"),
                    "BV/share": st.column_config.NumberColumn(format="$%.2f"),
                    "TBV/share": st.column_config.NumberColumn(format="$%.2f"),
                    "ROE": st.column_config.NumberColumn(format="%.2f%%"),
                    "ROA": st.column_config.NumberColumn(format="%.2f%%"),
                    "DPS": st.column_config.NumberColumn(format="$%.2f"),
                },
            )
        if fund.notes:
            with st.expander("Assumptions / notes"):
                for n in fund.notes:
                    st.markdown(f"- {n}")
        if result.extras.get("cet1_ratio"):
            st.success(f"**CET1 ratio (regex from latest 10-K):** {result.extras['cet1_ratio']:.2f}%")
    with tabs[3]:
        if result.seeking_alpha_headlines:
            for h in result.seeking_alpha_headlines[:10]:
                with st.container(border=True):
                    st.markdown(f"**[{h.title}]({h.link})**")
                    if h.published:
                        st.caption(h.published[:25])
        else:
            st.info("No public Seeking Alpha headlines retrieved.")


# ============================================================================
#                                   ROUTING
# ============================================================================
if st.session_state.view == "screener":
    render_screener(chosen_segments=chosen_segments, chart_theme=chart_theme)
else:
    render_detail(st.session_state.drill_ticker or "JPM", chart_theme=chart_theme)
