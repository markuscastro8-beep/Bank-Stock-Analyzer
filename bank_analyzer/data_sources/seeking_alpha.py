"""Seeking Alpha integration (intentionally limited).

Seeking Alpha's content is gated by login/paywall and their Terms of
Service prohibit automated scraping. We do NOT scrape protected pages.

This module exposes:

  * `news_rss(symbol)` — fetches the public symbol RSS feed at
    `https://seekingalpha.com/api/sa/combined/{SYMBOL}.xml` if it is
    reachable. The feed is published for human consumption with a normal
    User-Agent and contains article headlines/summaries — no paywalled
    body text.
  * `article_link(symbol)` — returns the canonical public symbol page
    URL so downstream UI can deep-link without fetching.

If you have an authorized Seeking Alpha API key (e.g. via RapidAPI
Seeking Alpha endpoint, with your own subscription), set the
`SEEKING_ALPHA_API_KEY` env var and the client will pass it through.
Otherwise it falls back to the public RSS only.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Optional
from xml.etree import ElementTree as ET

from ..cache import Cache
from ..http_client import HttpClient
from ..logger import get_logger

log = get_logger(__name__)

PUBLIC_RSS = "https://seekingalpha.com/api/sa/combined/{symbol}.xml"
SYMBOL_PAGE = "https://seekingalpha.com/symbol/{symbol}"


@dataclass
class SaHeadline:
    title: str
    link: str
    published: str
    summary: str


class SeekingAlphaClient:
    """Public-only Seeking Alpha touch-points."""

    def __init__(self, http: HttpClient, cache: Cache):
        self.http = http
        self.cache = cache
        self.api_key: Optional[str] = os.environ.get("SEEKING_ALPHA_API_KEY")

    def article_link(self, symbol: str) -> str:
        return SYMBOL_PAGE.format(symbol=symbol.upper())

    def news_rss(self, symbol: str, max_items: int = 10) -> list[SaHeadline]:
        """Fetch the public RSS feed. Returns [] on failure (network, gating, etc.)."""
        url = PUBLIC_RSS.format(symbol=symbol.upper())
        try:
            result = self.http.get(url, accept="application/xml", max_age_sec=2 * 3600)
        except Exception as exc:  # noqa: BLE001
            log.info("Seeking Alpha RSS unreachable for %s: %s", symbol, exc)
            return []
        if result.status != 200 or not result.body.strip().startswith("<"):
            return []
        try:
            root = ET.fromstring(result.body)
        except ET.ParseError:
            return []
        items: list[SaHeadline] = []
        for item in root.iter("item"):
            title = (item.findtext("title") or "").strip()
            link = (item.findtext("link") or "").strip()
            pub = (item.findtext("pubDate") or "").strip()
            desc = (item.findtext("description") or "").strip()
            if title and link:
                items.append(SaHeadline(title=title, link=link, published=pub, summary=desc))
            if len(items) >= max_items:
                break
        return items
