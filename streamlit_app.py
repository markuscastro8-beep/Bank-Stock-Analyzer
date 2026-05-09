"""Streamlit dashboard front-end.

Run with:  streamlit run streamlit_app.py
"""
from __future__ import annotations

import os

import streamlit as st
import streamlit.components.v1 as components

# Bridge Streamlit Cloud "Secrets" → environment variables BEFORE the
# analyzer imports load_config (which reads SEC_USER_AGENT from os.environ).
# Locally, st.secrets is empty and this is a no-op.
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

# --------------------------------------------------------------------------- page
st.set_page_config(
    page_title="Bank Stock Analyzer",
    page_icon="🏦",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Subtle CSS polish: tighter metric cards, better divider color, no ugly link
# underlines on the metric labels.
st.markdown(
    """
    <style>
      .stMetric { background: #f8fafc; border: 1px solid #e2e8f0;
                  border-radius: 10px; padding: 14px 16px; }
      .stMetric label { color: #475569 !important; font-weight: 500 !important; }
      .stMetric [data-testid="stMetricValue"] { font-size: 1.6rem !important; }
      .stTabs [data-baseweb="tab-list"] { gap: 8px; }
      .stTabs [data-baseweb="tab"] { padding: 10px 16px; }
      hr { border-color: #e2e8f0 !important; }
      .ticker-chip button { width: 100%; }
    </style>
    """,
    unsafe_allow_html=True,
)


# --------------------------------------------------------------------------- session
if "ticker" not in st.session_state:
    st.session_state.ticker = "JPM"


@st.cache_resource(show_spinner=False)
def get_analyzer() -> Analyzer:
    return Analyzer(load_config())


@st.cache_data(show_spinner="Pulling SEC + Yahoo data...", ttl=60 * 60)
def cached_analyze(ticker: str):
    return get_analyzer().analyze(ticker)


@st.cache_data(show_spinner=False, ttl=60 * 60)
def cached_validate(ticker: str):
    return get_analyzer().validate_ticker(ticker)


# --------------------------------------------------------------------------- sidebar
PRESET_TICKERS = {
    "Big four (JPM/BAC/WFC/C)": ["JPM", "BAC", "WFC", "C"],
    "Super-regionals": ["USB", "PNC", "TFC", "FITB", "RF", "MTB"],
    "Trust & custody": ["BK", "STT", "NTRS"],
}

with st.sidebar:
    st.title("🏦 Bank Stock Analyzer")
    st.caption("SEC EDGAR fundamentals · Yahoo prices · TradingView charts")

    st.markdown("**Choose a ticker**")

    with st.form("ticker_form", clear_on_submit=False):
        ticker_input = st.text_input(
            "Ticker symbol",
            value=st.session_state.ticker,
            placeholder="e.g. JPM, BAC, WFC, C",
            label_visibility="collapsed",
        ).strip().upper()
        submitted = st.form_submit_button("Analyze →", type="primary", use_container_width=True)
    if submitted and ticker_input:
        st.session_state.ticker = ticker_input

    st.markdown("**Quick-pick popular bank tickers**")
    for group_name, tickers in PRESET_TICKERS.items():
        st.caption(group_name)
        cols = st.columns(len(tickers))
        for col, t in zip(cols, tickers):
            with col:
                if st.button(t, key=f"chip_{t}", use_container_width=True):
                    st.session_state.ticker = t
                    st.rerun()

    st.divider()

    peers_input = st.text_input(
        "Peers (comma separated)",
        value="BAC, WFC, C",
        help="Used in the Peers tab. Leave empty to skip.",
    )

    chart_theme = st.selectbox("Chart theme", ["light", "dark"], index=0)
    show_peers_tab = st.checkbox("Run peer comparison", value=True)

    st.divider()
    st.caption(
        "Data: SEC EDGAR `companyfacts` XBRL · Yahoo Finance via yfinance · "
        "TradingView Advanced Chart widget. SEC user-agent identifies you."
    )


# --------------------------------------------------------------------------- main
ticker = st.session_state.ticker
if not ticker:
    st.info("Pick or type a ticker in the sidebar to get started.")
    st.stop()

ok, reason = cached_validate(ticker)
if not ok:
    st.error(f"Could not validate ticker `{ticker}`: {reason}")
    st.stop()

result = cached_analyze(ticker)
fund = result.fundamentals
tech = result.technicals
latest = fund.latest


# -------------------------------------------------------------- header & metrics
left, right = st.columns([3, 1])
with left:
    st.markdown(f"## {result.ticker} — {result.company_name}")
    st.caption(
        f"Currently showing **{result.ticker}**. "
        f"Type a different ticker in the sidebar to switch."
    )
with right:
    if result.yahoo_info.get("website"):
        st.markdown(f"[Company website]({result.yahoo_info['website']})")
    st.markdown(f"[SEC filings]({result.sec.info.edgar_url})")

# Big metric tiles
def _delta_pct(current, previous):
    if current is None or previous is None or previous == 0:
        return None
    return f"{(current / previous - 1) * 100:+.2f}%"

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Last close", f"${tech.last_close:,.2f}" if tech.last_close else "—")
m2.metric(
    "TTM EPS",
    f"${fund.ttm_eps:,.2f}" if fund.ttm_eps is not None else "—",
)
if tech.last_close and fund.ttm_eps:
    m3.metric("P/E (TTM)", f"{tech.last_close / fund.ttm_eps:,.2f}")
else:
    m3.metric("P/E (TTM)", "—")
if latest and latest.tangible_book_value_per_share and tech.last_close:
    m4.metric(
        "P/TBV",
        f"{tech.last_close / latest.tangible_book_value_per_share:,.2f}",
    )
else:
    m4.metric("P/TBV", "—")
dy = result.yahoo_info.get("dividendYield")
m5.metric(
    "Dividend yield",
    f"{dy * 100:,.2f}%" if dy else "—",
)

m6, m7, m8, m9, m10 = st.columns(5)
m6.metric(
    "52-week high",
    f"${tech.high_52w:,.2f}" if tech.high_52w else "—",
)
m7.metric(
    "52-week low",
    f"${tech.low_52w:,.2f}" if tech.low_52w else "—",
)
m8.metric(
    "MA50 (today)",
    f"${tech.ma_values.get(50):,.2f}" if tech.ma_values.get(50) else "—",
)
m9.metric(
    "MA200 (today)",
    f"${tech.ma_values.get(200):,.2f}" if tech.ma_values.get(200) else "—",
)
mc = result.yahoo_info.get("marketCap")
m10.metric(
    "Market cap",
    f"${mc / 1e9:,.1f}B" if mc else "—",
)

st.divider()

# --------------------------------------------------------------------------- tabs
tab_tv, tab_history, tab_fund, tab_news, tab_peers = st.tabs(
    [
        "📊 TradingView",
        "📈 5-Year history",
        "💰 Fundamentals",
        "📰 News",
        "🏦 Peers",
    ]
)

# ---------- Tab 1: TradingView widget ---------------------------------------
with tab_tv:
    st.markdown(
        f"### Live TradingView chart — {result.ticker}"
        f"  \n*Resizable, draggable, real-time. Includes MA20, MA50, MA200 by default. "
        f"You can change the symbol directly inside the widget too.*"
    )
    components.html(
        advanced_chart_html(
            result.ticker,
            theme=chart_theme,
            height=620,
            moving_averages=(20, 50, 200),
        ),
        height=640,
        scrolling=False,
    )

# ---------- Tab 2: 5-year history -------------------------------------------
with tab_history:
    st.markdown(
        f"### 5-year price history with moving averages"
        f"  \n*Data: Yahoo Finance via `yfinance`. "
        f"MAs shown: 20-day (short), 50-day (medium), 200-day (long), 252-day (≈1y).*"
    )
    fig = build_plotly_chart(
        tech.history,
        title=f"{result.ticker} — {result.company_name} (5y)",
        moving_averages=(20, 50, 200, 252),
    )
    fig.update_layout(template=f"plotly_{chart_theme}")
    st.plotly_chart(fig, use_container_width=True)

    with st.expander("Latest moving-average values"):
        ma_cols = st.columns(len(tech.ma_values))
        for col, (window, val) in zip(ma_cols, tech.ma_values.items()):
            label = f"MA{window}"
            if window == 252:
                label += " (~1y)"
            col.metric(label, f"${val:,.2f}" if val else "—")

# ---------- Tab 3: Fundamentals ---------------------------------------------
with tab_fund:
    st.markdown(
        f"### Last {len(fund.years)} fiscal years — from SEC EDGAR XBRL `companyfacts`"
    )

    rows = []
    for y in fund.years:
        rows.append(
            {
                "Fiscal year": f"FY{y.fiscal_year}",
                "Period end": y.period_end,
                "Net income": y.net_income,
                "NI to common": y.net_income_to_common,
                "Total assets": y.total_assets,
                "Common equity": y.common_equity,
                "Goodwill": y.goodwill,
                "Intangibles": y.intangibles,
                "Shares (EoP)": y.shares_eop,
                "EPS basic": y.eps_basic,
                "EPS diluted": y.eps_diluted,
                "EPS growth": y.eps_growth,
                "BV/share": y.book_value_per_share,
                "TBV/share": y.tangible_book_value_per_share,
                "ROE": y.roe,
                "ROA": y.roa,
                "DPS (declared)": y.dividends_per_share,
            }
        )
    if rows:
        st.dataframe(
            rows,
            use_container_width=True,
            hide_index=True,
            column_config={
                "Net income": st.column_config.NumberColumn(format="$%.0f"),
                "NI to common": st.column_config.NumberColumn(format="$%.0f"),
                "Total assets": st.column_config.NumberColumn(format="$%.0f"),
                "Common equity": st.column_config.NumberColumn(format="$%.0f"),
                "Goodwill": st.column_config.NumberColumn(format="$%.0f"),
                "Intangibles": st.column_config.NumberColumn(format="$%.0f"),
                "Shares (EoP)": st.column_config.NumberColumn(format="%.0f"),
                "EPS basic": st.column_config.NumberColumn(format="$%.2f"),
                "EPS diluted": st.column_config.NumberColumn(format="$%.2f"),
                "EPS growth": st.column_config.NumberColumn(format="%.2f%%"),
                "BV/share": st.column_config.NumberColumn(format="$%.2f"),
                "TBV/share": st.column_config.NumberColumn(format="$%.2f"),
                "ROE": st.column_config.NumberColumn(format="%.2f%%"),
                "ROA": st.column_config.NumberColumn(format="%.2f%%"),
                "DPS (declared)": st.column_config.NumberColumn(format="$%.2f"),
            },
        )

    if fund.notes:
        with st.expander("Assumptions / parsing notes"):
            for n in fund.notes:
                st.markdown(f"- {n}")

    if result.extras.get("cet1_ratio"):
        st.success(
            f"**CET1 ratio (regex from latest 10-K):** "
            f"{result.extras['cet1_ratio']:.2f}%"
        )
        with st.expander("Excerpt from filing"):
            st.code(result.extras.get("cet1_excerpt", ""))

    if result.sec.filings_10k:
        st.markdown("**Source 10-K filings:**")
        for f in result.sec.filings_10k:
            yr = f.report_date.year if f.report_date else f.filing_date.year if f.filing_date else "?"
            st.markdown(f"- FY{yr} · {f.form} · filed {f.filing_date} · `{f.accession}`")

# ---------- Tab 4: News -----------------------------------------------------
with tab_news:
    st.markdown(f"### Recent headlines for {result.ticker}")
    if result.seeking_alpha_headlines:
        for h in result.seeking_alpha_headlines[:12]:
            with st.container(border=True):
                st.markdown(f"**[{h.title}]({h.link})**")
                if h.published:
                    st.caption(h.published[:25])
                if h.summary:
                    st.caption(h.summary[:240] + ("…" if len(h.summary) > 240 else ""))
    else:
        st.info(
            "No public Seeking Alpha headlines retrieved. The public RSS endpoint "
            "may be temporarily unavailable for this ticker."
        )
    st.markdown(f"[Open Seeking Alpha symbol page →]({result.seeking_alpha_link})")

# ---------- Tab 5: Peers ----------------------------------------------------
with tab_peers:
    if not show_peers_tab:
        st.info("Peer comparison disabled in the sidebar.")
    else:
        peers = [p.strip().upper() for p in peers_input.split(",") if p.strip()]
        peers = [p for p in peers if p != result.ticker]
        if not peers:
            st.info("Add comma-separated peer tickers in the sidebar.")
        else:
            st.markdown(f"### {result.ticker} vs. {', '.join(peers)}")
            with st.spinner("Pulling peer data..."):
                peer_results = {result.ticker: result}
                for p in peers:
                    try:
                        peer_results[p] = cached_analyze(p)
                    except Exception as exc:  # noqa: BLE001
                        st.warning(f"Skipped {p}: {exc}")

            # Comparison table
            peer_rows = []
            for t, r in peer_results.items():
                lt = r.fundamentals.latest
                last_close = r.technicals.last_close or 0.0
                peer_rows.append(
                    {
                        "Ticker": t,
                        "Last close": last_close,
                        "TTM EPS": r.fundamentals.ttm_eps,
                        "BV/share": lt.book_value_per_share if lt else None,
                        "TBV/share": lt.tangible_book_value_per_share if lt else None,
                        "ROE": lt.roe if lt else None,
                        "ROA": lt.roa if lt else None,
                        "P/TBV": (
                            last_close / lt.tangible_book_value_per_share
                            if lt and lt.tangible_book_value_per_share
                            else None
                        ),
                        "Div yield": r.yahoo_info.get("dividendYield"),
                    }
                )
            st.dataframe(
                peer_rows,
                use_container_width=True,
                hide_index=True,
                column_config={
                    "Last close": st.column_config.NumberColumn(format="$%.2f"),
                    "TTM EPS": st.column_config.NumberColumn(format="$%.2f"),
                    "BV/share": st.column_config.NumberColumn(format="$%.2f"),
                    "TBV/share": st.column_config.NumberColumn(format="$%.2f"),
                    "ROE": st.column_config.NumberColumn(format="%.2f%%"),
                    "ROA": st.column_config.NumberColumn(format="%.2f%%"),
                    "P/TBV": st.column_config.NumberColumn(format="%.2f"),
                    "Div yield": st.column_config.NumberColumn(format="%.2f%%"),
                },
            )

            # Mini TradingView charts side by side
            st.markdown("**Side-by-side TradingView mini-charts (12-month)**")
            mc_cols = st.columns(min(len(peer_results), 4))
            for col, (t, _r) in zip(mc_cols, peer_results.items()):
                with col:
                    st.caption(t)
                    components.html(
                        mini_chart_html(t, theme=chart_theme, height=200),
                        height=220,
                        scrolling=False,
                    )
