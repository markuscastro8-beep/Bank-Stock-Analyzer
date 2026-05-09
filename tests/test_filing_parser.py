"""Tests for the raw-filing fallback parser."""
from __future__ import annotations

from bank_analyzer.sec_parser.filing_parser import RawFilingFallback


def test_cet1_regex_extraction_simple():
    html = """
    <html><body>
      <p>The Common Equity Tier 1 capital ratio was 13.8% at December 31, 2023.</p>
    </body></html>
    """
    fb = RawFilingFallback(html)
    hit = fb.find_cet1_ratio()
    assert hit is not None
    assert hit.value == 13.8


def test_cet1_regex_no_match_returns_none():
    fb = RawFilingFallback("<html><body><p>No regulatory ratios discussed here.</p></body></html>")
    assert fb.find_cet1_ratio() is None


def test_empty_html_returns_none():
    assert RawFilingFallback("").find_cet1_ratio() is None
