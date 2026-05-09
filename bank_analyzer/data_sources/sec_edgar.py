"""SEC EDGAR client.

Public endpoints used (no auth required, but the User-Agent must identify
the requester per https://www.sec.gov/os/accessing-edgar-data):

  - https://www.sec.gov/files/company_tickers.json    (ticker -> CIK map)
  - https://data.sec.gov/submissions/CIK{cik10}.json  (filing list)
  - https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json
        (all XBRL facts, every period, every concept — the goldmine)

We rely on companyfacts for accounting metrics rather than parsing 10-K
HTML/XBRL ZIP archives, because companyfacts already returns normalized
us-gaap concepts with units, periods, and form references. We *do* fetch
the filing index for the latest 10-K so we can show users links and pick
up missing concepts via the per-filing XBRL companyconcept endpoint.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Iterable, Optional

from ..cache import Cache
from ..http_client import HttpClient
from ..logger import get_logger

log = get_logger(__name__)

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik10}.json"
COMPANY_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik10}.json"
COMPANY_CONCEPT_URL = (
    "https://data.sec.gov/api/xbrl/companyconcept/CIK{cik10}/us-gaap/{concept}.json"
)


@dataclass
class CompanyInfo:
    cik: str
    cik10: str
    ticker: str
    name: str

    @property
    def edgar_url(self) -> str:
        return f"https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK={self.cik10}&type=10-K"


@dataclass
class Filing:
    accession: str
    form: str
    filing_date: date
    report_date: Optional[date]
    primary_document: str
    primary_doc_description: str

    @property
    def index_url(self) -> str:
        acc_no_dashes = self.accession.replace("-", "")
        # Filings live at /Archives/edgar/data/<cik>/<accession-no-dashes>/
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{int(self._cik):d}/{acc_no_dashes}/{self.primary_document}"
        )

    # set later by client
    _cik: str = ""


@dataclass
class SecCompanyData:
    info: CompanyInfo
    filings_10k: list[Filing] = field(default_factory=list)
    company_facts: dict[str, Any] = field(default_factory=dict)


class SecEdgarClient:
    """Client over the public EDGAR endpoints."""

    def __init__(self, http: HttpClient, cache: Cache):
        self.http = http
        self.cache = cache

    # ------------------------------------------------------------------ tickers
    def _ticker_map(self) -> dict[str, dict[str, Any]]:
        cached = self.cache.get_json("sec", "tickers", max_age_sec=7 * 24 * 3600)
        if cached:
            return cached
        result = self.http.get(TICKERS_URL, max_age_sec=7 * 24 * 3600)
        if result.status != 200:
            raise RuntimeError(f"Failed to fetch SEC ticker map: {result.status}")
        raw = json.loads(result.body)
        # raw is keyed by row index → {cik_str, ticker, title}
        normalized = {
            entry["ticker"].upper(): {
                "cik": str(entry["cik_str"]),
                "ticker": entry["ticker"].upper(),
                "name": entry["title"],
            }
            for entry in raw.values()
        }
        self.cache.put_json("sec", "tickers", normalized)
        return normalized

    def lookup_ticker(self, ticker: str) -> CompanyInfo:
        ticker = ticker.strip().upper()
        if not ticker or not ticker.replace(".", "").replace("-", "").isalnum():
            raise ValueError(f"Invalid ticker symbol: {ticker!r}")
        mapping = self._ticker_map()
        entry = mapping.get(ticker)
        if not entry:
            raise ValueError(f"Ticker {ticker!r} not found in SEC EDGAR registry")
        cik = entry["cik"]
        cik10 = cik.zfill(10)
        return CompanyInfo(cik=cik, cik10=cik10, ticker=ticker, name=entry["name"])

    # ------------------------------------------------------------------ submissions
    def fetch_submissions(self, cik10: str) -> dict[str, Any]:
        url = SUBMISSIONS_URL.format(cik10=cik10)
        result = self.http.get(url, max_age_sec=24 * 3600)
        if result.status != 200:
            raise RuntimeError(f"Failed to fetch submissions for {cik10}: {result.status}")
        return json.loads(result.body)

    def latest_10k_filings(self, cik10: str, limit: int = 3) -> list[Filing]:
        """Return the `limit` most recent 10-K filings."""
        data = self.fetch_submissions(cik10)
        recent = data.get("filings", {}).get("recent", {})
        forms = recent.get("form", [])
        accs = recent.get("accessionNumber", [])
        fdates = recent.get("filingDate", [])
        rdates = recent.get("reportDate", [])
        primary_docs = recent.get("primaryDocument", [])
        primary_descs = recent.get("primaryDocDescription", [])

        out: list[Filing] = []
        for i, form in enumerate(forms):
            if form not in ("10-K", "10-K/A"):
                continue
            try:
                fd = date.fromisoformat(fdates[i]) if fdates[i] else None
                rd = date.fromisoformat(rdates[i]) if rdates[i] else None
            except (TypeError, ValueError):
                fd, rd = None, None
            filing = Filing(
                accession=accs[i],
                form=form,
                filing_date=fd,
                report_date=rd,
                primary_document=primary_docs[i] if i < len(primary_docs) else "",
                primary_doc_description=(
                    primary_descs[i] if i < len(primary_descs) else ""
                ),
            )
            filing._cik = str(int(cik10))
            out.append(filing)
            if len(out) >= limit:
                break
        return out

    # ------------------------------------------------------------------ companyfacts
    def fetch_company_facts(self, cik10: str) -> dict[str, Any]:
        """Fetch the companyfacts XBRL JSON for the given CIK (10-digit).

        Cached for 24 hours. Returns the parsed JSON.
        """
        url = COMPANY_FACTS_URL.format(cik10=cik10)
        result = self.http.get(url, max_age_sec=24 * 3600)
        if result.status != 200:
            raise RuntimeError(f"companyfacts fetch failed for {cik10}: {result.status}")
        return json.loads(result.body)

    # ------------------------------------------------------------------ aggregate
    def gather(self, ticker: str, fiscal_years: int = 3) -> SecCompanyData:
        info = self.lookup_ticker(ticker)
        filings = self.latest_10k_filings(info.cik10, limit=fiscal_years)
        facts = self.fetch_company_facts(info.cik10)
        return SecCompanyData(info=info, filings_10k=filings, company_facts=facts)

    # ------------------------------------------------------------------ raw filing
    def fetch_filing_text(self, filing: Filing) -> str:
        """Best-effort raw fetch of a 10-K primary document for fallback parsing."""
        url = filing.index_url
        result = self.http.get(url, accept="text/html", max_age_sec=30 * 24 * 3600)
        if result.status != 200:
            log.warning("filing fetch failed for %s: %s", url, result.status)
            return ""
        return result.body

    # ------------------------------------------------------------------ helpers
    @staticmethod
    def concept_units(facts: dict[str, Any], concepts: Iterable[str]) -> dict[str, list[dict]]:
        """Return raw `us-gaap` concept rows for any of the given concept names.

        Output: {concept_name: [ {end, val, fy, fp, form, accn}, ... ] }
        """
        gaap = facts.get("facts", {}).get("us-gaap", {})
        out: dict[str, list[dict]] = {}
        for c in concepts:
            entry = gaap.get(c)
            if not entry:
                continue
            units = entry.get("units", {})
            # Pick the first available unit (USD, shares, USD/shares, etc.).
            for _unit_name, rows in units.items():
                out[c] = rows
                break
        return out
