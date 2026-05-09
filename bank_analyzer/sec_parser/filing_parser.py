"""Fallback parsing of raw 10-K HTML filings.

Used only when XBRL companyfacts data is missing for a concept. We do
text-based extraction of a small number of bank-specific items that XBRL
tagging often misses (e.g., CET1 ratio in narrative tables).

Limitations: 10-K HTML varies wildly across filers; this is best-effort
and clearly marked as such in returned values.
"""
from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Optional

from bs4 import BeautifulSoup

from ..logger import get_logger

log = get_logger(__name__)


@dataclass
class FallbackHit:
    metric: str
    value: float
    excerpt: str
    confidence: str  # "low" | "medium" | "high"


_CET1_RE = re.compile(
    r"(?:common\s+equity\s+tier\s*1|cet\s*1)\s+(?:capital\s+)?ratio[^0-9]{0,80}"
    r"(\d{1,2}\.\d{1,2})\s*%",
    re.IGNORECASE | re.DOTALL,
)


class RawFilingFallback:
    """Best-effort regex/text scrape of a 10-K primary document."""

    def __init__(self, html: str):
        self.html = html or ""
        self._text: Optional[str] = None

    @property
    def text(self) -> str:
        if self._text is None:
            if not self.html:
                self._text = ""
            else:
                soup = BeautifulSoup(self.html, "lxml")
                # Strip script/style; flatten whitespace.
                for tag in soup(["script", "style"]):
                    tag.decompose()
                self._text = re.sub(r"\s+", " ", soup.get_text(" "))
        return self._text

    def find_cet1_ratio(self) -> Optional[FallbackHit]:
        if not self.text:
            return None
        m = _CET1_RE.search(self.text)
        if not m:
            return None
        try:
            value = float(m.group(1))
        except ValueError:
            return None
        start = max(0, m.start() - 60)
        end = min(len(self.text), m.end() + 30)
        excerpt = self.text[start:end].strip()
        return FallbackHit(
            metric="cet1_ratio",
            value=value,
            excerpt=excerpt,
            confidence="medium",
        )
