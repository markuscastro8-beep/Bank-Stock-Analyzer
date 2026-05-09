"""Tests for the SQLite cache."""
from __future__ import annotations

import time
from pathlib import Path

from bank_analyzer.cache import Cache


def test_http_cache_roundtrip(tmp_path: Path):
    cache = Cache(tmp_path / "c.sqlite")
    cache.put_http("https://example.com/x", "hello", 200)
    assert cache.get_http("https://example.com/x") == "hello"


def test_http_cache_max_age(tmp_path: Path):
    cache = Cache(tmp_path / "c.sqlite")
    cache.put_http("https://example.com/x", "hello", 200)
    time.sleep(0.05)
    assert cache.get_http("https://example.com/x", max_age_sec=0.01) is None


def test_json_cache_roundtrip(tmp_path: Path):
    cache = Cache(tmp_path / "c.sqlite")
    payload = {"a": 1, "b": [1, 2, 3]}
    cache.put_json("ns", "k", payload)
    assert cache.get_json("ns", "k") == payload


def test_error_responses_not_cached(tmp_path: Path):
    cache = Cache(tmp_path / "c.sqlite")
    cache.put_http("https://example.com/x", "boom", 500)
    assert cache.get_http("https://example.com/x") is None
