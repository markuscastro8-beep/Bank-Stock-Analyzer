# Bank Stock Analyzer

A modular, production-quality Python application for fundamental + technical
analysis of U.S. bank stocks, sourcing accounting data from **SEC EDGAR**
(XBRL `companyfacts`), prices from **Yahoo Finance** (via `yfinance`), and
optional public headlines from **Seeking Alpha**'s public RSS feed. Charts
are rendered with `mplfinance` (PNGs) and `plotly` (interactive), with a
TradingView-compatible JSON payload generator for the lightweight-charts
JS library.

> Designed for tickers like **JPM, BAC, WFC, C, USB, PNC, TFC**, but it works
> for any U.S. issuer that files 10-K reports with the SEC.

---

## Project layout

```
bank_stock_analyzer/
├── main.py                      # CLI entry point
├── streamlit_app.py             # Streamlit dashboard
├── config.yaml                  # runtime config (overridable via env)
├── requirements.txt
├── .env.example
├── pytest.ini
├── bank_analyzer/
│   ├── analyzer.py              # top-level orchestration
│   ├── config.py                # config loader (yaml + env)
│   ├── cache.py                 # SQLite response cache
│   ├── http_client.py           # polite HTTP w/ retry + cache
│   ├── logger.py
│   ├── data_sources/
│   │   ├── sec_edgar.py
│   │   ├── yahoo_finance.py
│   │   └── seeking_alpha.py
│   ├── sec_parser/
│   │   ├── taxonomy.py          # XBRL concept aliases
│   │   ├── xbrl_parser.py       # companyfacts → metric series
│   │   └── filing_parser.py     # raw 10-K HTML fallback
│   ├── calculations/
│   │   ├── fundamentals.py      # EPS, BV/sh, TBV/sh, ROE, ROA, …
│   │   └── technicals.py        # MAs + price summary
│   ├── charts/
│   │   ├── candlestick.py       # mplfinance PNG
│   │   └── plotly_charts.py     # plotly + lightweight-charts payload
│   └── ui/
│       ├── terminal.py          # rich tables
│       └── reports.py           # Excel + PDF exporters
├── tests/
│   ├── test_xbrl_parser.py
│   ├── test_fundamentals.py
│   ├── test_technicals.py
│   ├── test_filing_parser.py
│   └── test_cache.py
└── examples/                    # generated PNGs / sample reports go here
```

---

## Setup

```bash
# 1. Clone & enter the project
cd bank_stock_analyzer

# 2. Create a virtualenv (any flavor)
python -m venv .venv
source .venv/bin/activate              # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Copy the environment template and fill in YOUR contact info.
#    The SEC requires a descriptive User-Agent identifying the requester.
cp .env.example .env
# then edit .env and replace the placeholder email.
```

> **Important:** The `SEC_USER_AGENT` must contain a real contact email per
> https://www.sec.gov/os/accessing-edgar-data. Requests without one may be
> throttled or blocked.

---

## Running

### Command line

```bash
# Interactive prompt
python main.py

# Direct
python main.py JPM

# With Excel + PDF exports and a chart
python main.py JPM --excel --pdf

# With peer comparison
python main.py JPM --peers BAC WFC C
```

Outputs are written to `./output/`:

* `JPM_candles.png` — annotated candlestick chart with 20/50/200-day MAs
* `JPM_report.xlsx` — formatted Excel workbook (overview, fundamentals,
  prices, yahoo_info, notes)
* `JPM_report.pdf`  — one-page PDF summary including the chart

### Streamlit dashboard

```bash
streamlit run streamlit_app.py
```

Open the URL Streamlit prints (default `http://localhost:8501`), enter a
ticker in the sidebar, optionally add comma-separated peers, and click
**Analyze**.

### Tests

```bash
pytest
```

Tests run entirely offline using synthetic data; no network calls.

---

## What gets calculated

For each of the **last 3 fiscal years** (configurable):

| Metric                             | Formula                                                                 |
|------------------------------------|-------------------------------------------------------------------------|
| EPS basic                          | `NIToCommon / WeightedAvgSharesBasic` (or reported `EarningsPerShareBasic`) |
| EPS diluted                        | analogous, diluted shares                                               |
| EPS growth (YoY)                   | `EPS_t / EPS_{t-1} − 1`                                                 |
| TTM EPS / EPS 12                   | sum of latest 4 quarterly EPS rows; falls back to most recent FY EPS    |
| Book Value Per Share               | `CommonEquity_eop / SharesOutstanding_eop`                              |
| Tangible Book Value Per Share      | `(CommonEquity − Goodwill − OtherIntangibles) / SharesOutstanding_eop`  |
| ROE                                | `NIToCommon / Avg(CommonEquity)`                                        |
| ROA                                | `NetIncome / Avg(TotalAssets)`                                          |
| P/B, P/TBV, P/E                    | derived from latest close (Yahoo) ÷ above                               |

`Avg(X)` is the simple average of beginning and ending balances. When a
prior-year value is missing we fall back to point-in-time.

### Bank-specific accounting assumptions

* **Common equity** is preferred over total stockholders' equity. We try
  the explicit `CommonStockholdersEquity` tag first, then derive
  `Total stockholders' equity − Preferred stock` if both are present,
  and finally fall back to `StockholdersEquity` with a recorded note in
  the result's `notes`.
* **Tangible common equity (TCE)** is computed from raw components rather
  than relying on a single (unreliable) tag: `Common equity − Goodwill −
  Other intangibles ex-goodwill`.
* **CET1 / regulatory ratios** are not consistently XBRL-tagged. We try a
  regex sweep over the latest 10-K primary document as a clearly-marked
  best-effort fallback.
* **Net income vs. NI to common**: ROE uses the figure available to common
  shareholders (`NetIncomeLossAvailableToCommonStockholdersBasic`) when
  reported; otherwise plain `NetIncomeLoss`.

These choices are documented inline in
[`bank_analyzer/calculations/fundamentals.py`](bank_analyzer/calculations/fundamentals.py)
and surfaced to the user as `notes` whenever a fallback is applied.

---

## Data sources & legal posture

* **SEC EDGAR** — the public `data.sec.gov` JSON endpoints (ticker map,
  submissions, `companyfacts`, `companyconcept`). All compliant with the
  [SEC fair access policy](https://www.sec.gov/os/accessing-edgar-data):
  descriptive `User-Agent`, single-threaded, ≤ 10 req/sec, with a local
  SQLite cache to minimize repeat requests.
* **Yahoo Finance** — via `yfinance`. Used for prices, dividends, and
  metadata (market cap, beta, dividend yield).
* **Seeking Alpha** — **public RSS feed only**
  (`/api/sa/combined/<SYMBOL>.xml`). We do **not** scrape paywalled or
  subscriber-only content. If you have a legitimate API key (e.g. via the
  RapidAPI Seeking Alpha endpoint with your own subscription), set
  `SEEKING_ALPHA_API_KEY` in `.env` — the client is designed to accept it,
  but is not required to function.
* **TradingView** — we generate a JSON payload conforming to the
  Lightweight Charts series format. No TradingView account or API key is
  required; the same JSON also feeds the optional `lightweight-charts`
  Python wrapper if you want a desktop renderer.

---

## Reliability features

* **SQLite caching** for SEC JSON, ticker maps, and Yahoo info/history.
  TTLs are tuned per resource (24 h for filings, 12 h for prices, 7 d for
  the ticker map).
* **Retry + exponential backoff** on transient HTTP errors (429, 5xx).
* **Rate limiting** in the polite range for both SEC and Yahoo.
* **Graceful fallbacks** when a concept tag is missing: alias chains,
  derived computations, or recorded `notes` so the user knows.
* **Logging** to `./logs/analyzer.log` (rotating, 2 MB × 3) plus console.
* **Type hints** throughout, dataclasses for structured payloads, unit
  tests for the parsing & calculation core.

---

## Bonus features

* `--peers` flag and Streamlit peer-comparison table — side-by-side
  P/TBV, ROE, ROA, TBV/share for an arbitrary peer set.
* P/TBV, P/B, P/E (TTM) ratios computed from the latest Yahoo close.
* Dividend yield surfaced from Yahoo `info`.
* CET1 ratio extraction via regex on the latest 10-K HTML when XBRL
  tagging is unavailable.
* Excel (multi-sheet) and PDF (with embedded chart) exports.

### Not included (intentional scope decisions)

* **Insider transaction summaries** — would require parsing Form 4 XML
  filings (a separate sub-system). The plumbing is here (the SEC client
  can fetch any filing); the parser is left as a follow-up because doing
  it well requires deduping reporting persons and aggregating across
  multiple filings per quarter, which we did not want to ship half-done.

---

## Example screenshots

After running `python main.py JPM --pdf --excel`, look in `./output/`:

```
output/
├── JPM_candles.png      ← embedded below in PDF
├── JPM_report.pdf
└── JPM_report.xlsx
```

The terminal output looks like this (Rich tables):

```
╭─────────────────────────────────────────╮
│  JPM — JPMORGAN CHASE & CO              │
│  Last close $XYZ.AB                     │
╰─────────────────────────────────────────╯
                Price Summary
┏━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Metric                ┃                 Value ┃
┡━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━┩
│ Last close            │              $XYZ.AB  │
│ 52-week high          │              $XYZ.AB  │
│ MA20 / MA50 / MA200   │             $… / $…   │
└───────────────────────┴───────────────────────┘
       Fundamentals (last 3 fiscal years)
┏━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━┳━━━━━━━━┓
┃ Metric               ┃ FY2023 ┃ FY2022 ┃ FY2021 ┃
┡━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━╇━━━━━━━━┩
│ Net income           │  $…B   │  $…B   │  $…B   │
│ Total assets         │  $…B   │  …     │  …     │
│ Book value / share   │ $…     │ $…     │ $…     │
│ Tangible BV / share  │ $…     │ $…     │ $…     │
│ ROE                  │ …%     │ …%     │ …%     │
│ ROA                  │ …%     │ …%     │ …%     │
└──────────────────────┴────────┴────────┴────────┘
```

---

## Constraints / good citizenship

* No scraping of subscriber-only or login-gated pages.
* Polite rate limits (SEC ≤ 10 r/s; we run at 8 r/s with backoff).
* Cached responses to avoid repeating identical requests.
* Descriptive `User-Agent` on every request.

---

## License

MIT (or whichever you prefer — adjust this line for your fork).
