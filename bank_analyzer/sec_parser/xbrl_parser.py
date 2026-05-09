"""XBRL fact extraction from the SEC companyfacts JSON.

The companyfacts payload is shaped roughly like:

    {
      "cik": 19617,
      "entityName": "JPMORGAN CHASE & CO",
      "facts": {
         "us-gaap": {
            "Assets": {
               "label": "...",
               "description": "...",
               "units": {
                  "USD": [
                    {"start": "...", "end": "2023-12-31", "val": ...,
                     "fy": 2023, "fp": "FY", "form": "10-K", "filed": "..."},
                    ...
                  ]
               }
            },
            ...
         },
         "dei": {...}
      }
    }

For each metric we want, we walk the alias list in `taxonomy.py`, then for
each matching concept we filter rows by form (`10-K`, `10-K/A`, optionally
`20-F`) and fiscal period (`FY` for full-year flow concepts, end-of-period
balances for stocks). The most recent row per fiscal year wins (e.g. a
10-K/A amendment supersedes the 10-K).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from ..logger import get_logger
from .taxonomy import CONCEPT_ALIASES

log = get_logger(__name__)

ANNUAL_FORMS = {"10-K", "10-K/A", "20-F", "20-F/A", "40-F", "40-F/A"}


@dataclass
class FactPoint:
    val: float
    end: str
    fy: Optional[int]
    fp: Optional[str]
    form: str
    accn: str
    concept: str
    unit: str

    @property
    def is_annual(self) -> bool:
        return self.form in ANNUAL_FORMS and (self.fp == "FY")


@dataclass
class FactSeries:
    """One metric across multiple fiscal years."""

    metric: str
    points: list[FactPoint] = field(default_factory=list)

    def by_fy(self) -> dict[int, FactPoint]:
        out: dict[int, FactPoint] = {}
        for p in self.points:
            if p.fy is None:
                continue
            existing = out.get(p.fy)
            # Prefer 10-K/A amendments over 10-K; otherwise prefer the most
            # recently filed point (heuristic: longer accession suffix sorts later).
            if existing is None or _row_priority(p) > _row_priority(existing):
                out[p.fy] = p
        return out

    def latest_n_years(self, n: int) -> list[FactPoint]:
        by_fy = self.by_fy()
        return [by_fy[fy] for fy in sorted(by_fy.keys(), reverse=True)[:n]]


def _row_priority(p: FactPoint) -> tuple[int, str]:
    return (1 if p.form.endswith("/A") else 0, p.accn)


class XbrlFactExtractor:
    """Pulls metric series out of a companyfacts payload."""

    def __init__(self, company_facts: dict[str, Any]):
        self.facts = company_facts.get("facts", {}).get("us-gaap", {})
        self.dei = company_facts.get("facts", {}).get("dei", {})

    def _iter_concept_rows(
        self, concept: str
    ) -> Iterable[tuple[str, str, dict[str, Any]]]:
        """Yield (taxonomy, unit, row) for the given concept.

        Looks first in us-gaap, then dei (for shares-outstanding-style data).
        """
        for taxonomy, store in (("us-gaap", self.facts), ("dei", self.dei)):
            entry = store.get(concept)
            if not entry:
                continue
            for unit_name, rows in (entry.get("units") or {}).items():
                for row in rows:
                    yield taxonomy, unit_name, row

    def extract(self, metric: str, *, annual_only: bool = True) -> FactSeries:
        aliases = CONCEPT_ALIASES.get(metric, [metric])
        series = FactSeries(metric=metric)
        for concept in aliases:
            for _tax, unit, row in self._iter_concept_rows(concept):
                form = row.get("form", "")
                fp = row.get("fp")
                if annual_only and (form not in ANNUAL_FORMS or fp != "FY"):
                    continue
                val = row.get("val")
                if val is None:
                    continue
                point = FactPoint(
                    val=float(val),
                    end=row.get("end", ""),
                    fy=row.get("fy"),
                    fp=fp,
                    form=form,
                    accn=row.get("accn", ""),
                    concept=concept,
                    unit=unit,
                )
                series.points.append(point)
            if series.points:
                # First alias that yielded data wins; do not blend across concepts.
                break
        if not series.points:
            log.debug("No XBRL data found for metric %s (tried %s)", metric, aliases)
        return series

    def extract_many(self, metrics: Iterable[str]) -> dict[str, FactSeries]:
        return {m: self.extract(m) for m in metrics}
