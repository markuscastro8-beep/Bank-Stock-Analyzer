"""XBRL concept alias mapping.

Different filers (and the same filer across years) use slightly different
us-gaap tags for the same logical metric. This module defines the
ordered list of concept names we try, in priority order, for each
metric. Bank-specific aliases come first when relevant.

Bank-specific accounting notes:
  * Banks report "Tangible Common Equity" (TCE) inconsistently. The most
    portable approach is to compute it as:
        Common Stockholders' Equity − Goodwill − Other Intangible Assets
    rather than relying on a single tag.
  * Some filers tag preferred-stock-inclusive equity under
    StockholdersEquity; the parent-only common figure is under
    StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest
    or CommonStockholdersEquity. We prefer the common figure.
  * EPS for banks is sometimes reported as "earnings allocated to common
    shareholders" — basic EPS suffices for our purposes; we use diluted
    when present.
"""
from __future__ import annotations

CONCEPT_ALIASES: dict[str, list[str]] = {
    "net_income": [
        "NetIncomeLoss",
        "ProfitLoss",
        "NetIncomeLossAvailableToCommonStockholdersBasic",
    ],
    "net_income_to_common": [
        "NetIncomeLossAvailableToCommonStockholdersBasic",
        "NetIncomeLossAvailableToCommonStockholdersDiluted",
        "NetIncomeLoss",
    ],
    "stockholders_equity": [
        "StockholdersEquity",
        "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest",
    ],
    "common_equity": [
        "CommonStockholdersEquity",
        "StockholdersEquity",
    ],
    "preferred_equity": [
        "PreferredStockValue",
        "PreferredStockValueOutstanding",
    ],
    "total_assets": [
        "Assets",
    ],
    "goodwill": [
        "Goodwill",
    ],
    "intangibles_ex_goodwill": [
        "IntangibleAssetsNetExcludingGoodwill",
        "FiniteLivedIntangibleAssetsNet",
    ],
    "shares_outstanding_eop": [
        "CommonStockSharesOutstanding",
        "EntityCommonStockSharesOutstanding",
    ],
    "weighted_avg_shares_basic": [
        "WeightedAverageNumberOfSharesOutstandingBasic",
    ],
    "weighted_avg_shares_diluted": [
        "WeightedAverageNumberOfDilutedSharesOutstanding",
    ],
    "eps_basic": [
        "EarningsPerShareBasic",
    ],
    "eps_diluted": [
        "EarningsPerShareDiluted",
    ],
    "dividends_per_share": [
        "CommonStockDividendsPerShareDeclared",
        "CommonStockDividendsPerShareCashPaid",
    ],
    # Bank-specific: regulatory capital. Often reported only in narrative
    # text or pillar 3 disclosures; XBRL tagging exists but is patchy.
    "cet1_ratio": [
        "TierOneRiskBasedCapitalToRiskWeightedAssets",
        "CommonEquityTierOneCapitalToRiskWeightedAssets",
    ],
}
