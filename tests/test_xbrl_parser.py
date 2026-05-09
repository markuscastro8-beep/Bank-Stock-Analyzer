"""Tests for XBRL fact extractor and concept aliasing."""
from __future__ import annotations

from bank_analyzer.sec_parser.xbrl_parser import XbrlFactExtractor


def _facts_payload() -> dict:
    return {
        "facts": {
            "us-gaap": {
                "Assets": {
                    "label": "Total Assets",
                    "units": {
                        "USD": [
                            {"end": "2021-12-31", "val": 100.0, "fy": 2021, "fp": "FY", "form": "10-K", "accn": "a1"},
                            {"end": "2022-12-31", "val": 110.0, "fy": 2022, "fp": "FY", "form": "10-K", "accn": "a2"},
                            {"end": "2023-12-31", "val": 120.0, "fy": 2023, "fp": "FY", "form": "10-K", "accn": "a3"},
                            # quarterly row should be ignored when annual_only=True
                            {"end": "2023-09-30", "val": 119.0, "fy": 2023, "fp": "Q3", "form": "10-Q", "accn": "a4"},
                        ]
                    },
                },
                "StockholdersEquity": {
                    "units": {
                        "USD": [
                            {"end": "2021-12-31", "val": 10.0, "fy": 2021, "fp": "FY", "form": "10-K", "accn": "b1"},
                            {"end": "2022-12-31", "val": 12.0, "fy": 2022, "fp": "FY", "form": "10-K", "accn": "b2"},
                            {"end": "2023-12-31", "val": 14.0, "fy": 2023, "fp": "FY", "form": "10-K", "accn": "b3"},
                            # 10-K/A amendment: should win over the original 10-K via row-priority logic
                            {"end": "2023-12-31", "val": 14.5, "fy": 2023, "fp": "FY", "form": "10-K/A", "accn": "b3a"},
                        ]
                    }
                },
            }
        }
    }


def test_extract_total_assets_picks_annual_only():
    ext = XbrlFactExtractor(_facts_payload())
    series = ext.extract("total_assets")
    fy_map = series.by_fy()
    assert set(fy_map.keys()) == {2021, 2022, 2023}
    assert fy_map[2023].val == 120.0
    assert fy_map[2023].form == "10-K"


def test_amendment_supersedes_original_10k():
    ext = XbrlFactExtractor(_facts_payload())
    series = ext.extract("stockholders_equity")
    fy_map = series.by_fy()
    assert fy_map[2023].val == 14.5
    assert fy_map[2023].form == "10-K/A"


def test_alias_fallback_for_common_equity():
    # No explicit CommonStockholdersEquity → should fall back to StockholdersEquity.
    ext = XbrlFactExtractor(_facts_payload())
    series = ext.extract("common_equity")
    fy_map = series.by_fy()
    assert 2023 in fy_map
    assert fy_map[2023].concept == "StockholdersEquity"


def test_latest_n_years_descending():
    ext = XbrlFactExtractor(_facts_payload())
    series = ext.extract("total_assets")
    last_two = series.latest_n_years(2)
    assert [p.fy for p in last_two] == [2023, 2022]
