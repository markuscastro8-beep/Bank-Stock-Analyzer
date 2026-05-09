"""SEC filing parsers (XBRL companyfacts + raw filing fallback)."""
from .xbrl_parser import XbrlFactExtractor, FactSeries
from .taxonomy import CONCEPT_ALIASES
from .filing_parser import RawFilingFallback

__all__ = ["XbrlFactExtractor", "FactSeries", "CONCEPT_ALIASES", "RawFilingFallback"]
