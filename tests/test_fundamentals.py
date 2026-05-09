"""Tests for fundamental calculations."""
from __future__ import annotations

import math

from bank_analyzer.calculations.fundamentals import compute_fundamentals


def _make_facts() -> dict:
    """Synthetic 4-year companyfacts payload — picks 3 most-recent years for the calc."""
    def fy(end, val, year):
        return {"end": end, "val": val, "fy": year, "fp": "FY", "form": "10-K", "accn": f"a{year}"}

    return {
        "facts": {
            "us-gaap": {
                "NetIncomeLoss": {
                    "units": {"USD": [
                        fy("2020-12-31", 1_000_000_000, 2020),
                        fy("2021-12-31", 1_200_000_000, 2021),
                        fy("2022-12-31", 1_500_000_000, 2022),
                        fy("2023-12-31", 1_650_000_000, 2023),
                    ]}
                },
                "Assets": {
                    "units": {"USD": [
                        fy("2020-12-31", 50_000_000_000, 2020),
                        fy("2021-12-31", 55_000_000_000, 2021),
                        fy("2022-12-31", 60_000_000_000, 2022),
                        fy("2023-12-31", 65_000_000_000, 2023),
                    ]}
                },
                "CommonStockholdersEquity": {
                    "units": {"USD": [
                        fy("2020-12-31", 5_000_000_000, 2020),
                        fy("2021-12-31", 5_500_000_000, 2021),
                        fy("2022-12-31", 6_000_000_000, 2022),
                        fy("2023-12-31", 6_400_000_000, 2023),
                    ]}
                },
                "Goodwill": {
                    "units": {"USD": [
                        fy("2021-12-31", 500_000_000, 2021),
                        fy("2022-12-31", 500_000_000, 2022),
                        fy("2023-12-31", 500_000_000, 2023),
                    ]}
                },
                "IntangibleAssetsNetExcludingGoodwill": {
                    "units": {"USD": [
                        fy("2021-12-31", 100_000_000, 2021),
                        fy("2022-12-31", 90_000_000, 2022),
                        fy("2023-12-31", 80_000_000, 2023),
                    ]}
                },
                "CommonStockSharesOutstanding": {
                    "units": {"shares": [
                        fy("2021-12-31", 1_000_000_000, 2021),
                        fy("2022-12-31", 1_000_000_000, 2022),
                        fy("2023-12-31", 1_000_000_000, 2023),
                    ]}
                },
                "WeightedAverageNumberOfSharesOutstandingBasic": {
                    "units": {"shares": [
                        fy("2020-12-31", 1_000_000_000, 2020),
                        fy("2021-12-31", 1_000_000_000, 2021),
                        fy("2022-12-31", 1_000_000_000, 2022),
                        fy("2023-12-31", 1_000_000_000, 2023),
                    ]}
                },
                "EarningsPerShareBasic": {
                    "units": {"USD/shares": [
                        fy("2020-12-31", 1.00, 2020),
                        fy("2021-12-31", 1.20, 2021),
                        fy("2022-12-31", 1.50, 2022),
                        fy("2023-12-31", 1.65, 2023),
                    ]}
                },
            }
        }
    }


def test_basic_calculations_three_years():
    fund = compute_fundamentals("BANK", _make_facts(), fiscal_years=3)
    assert [y.fiscal_year for y in fund.years] == [2023, 2022, 2021]

    latest = fund.latest
    assert latest is not None

    # Book value per share = 6.4B / 1B shares = 6.40
    assert math.isclose(latest.book_value_per_share, 6.40, rel_tol=1e-3)
    # Tangible BV / share = (6.4B - 0.5B - 0.08B) / 1B = 5.82
    assert math.isclose(latest.tangible_book_value_per_share, 5.82, rel_tol=1e-3)
    # ROE = NI / avg equity = 1.65B / ((6.0+6.4)/2)B = ~0.2661
    assert math.isclose(latest.roe, 1.65 / 6.20, rel_tol=1e-3)
    # ROA = 1.65B / ((60+65)/2)B
    assert math.isclose(latest.roa, 1.65 / 62.5, rel_tol=1e-3)
    # EPS growth from 1.50 -> 1.65 = 10%
    assert math.isclose(latest.eps_growth, 0.10, rel_tol=1e-3)


def test_eps_uses_reported_when_available():
    fund = compute_fundamentals("BANK", _make_facts(), fiscal_years=3)
    assert fund.latest.eps_basic == 1.65
