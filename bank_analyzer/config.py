"""Configuration loader.

Reads settings from `config.yaml` if present, then overlays values from the
process environment (which may have been populated from a `.env` file).
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml
from dotenv import load_dotenv

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_DEFAULT_CONFIG_PATH = _PROJECT_ROOT / "config.yaml"


@dataclass
class Config:
    """Runtime configuration for the analyzer."""

    sec_user_agent: str = "BankStockAnalyzer research@example.com"
    cache_dir: Path = _PROJECT_ROOT / ".cache"
    cache_db: Path = _PROJECT_ROOT / ".cache" / "analyzer.sqlite"
    output_dir: Path = _PROJECT_ROOT / "output"
    log_dir: Path = _PROJECT_ROOT / "logs"
    log_level: str = "INFO"

    sec_rate_limit_per_sec: float = 8.0  # SEC asks for <= 10 req/s
    yahoo_rate_limit_per_sec: float = 4.0
    request_timeout_sec: int = 20
    max_retries: int = 4
    backoff_base_sec: float = 1.5

    price_history_years: int = 5
    moving_averages: tuple[int, ...] = (20, 50, 200)
    fiscal_years: int = 3

    peer_groups: dict[str, list[str]] = field(default_factory=dict)

    def ensure_dirs(self) -> None:
        """Create cache, output, and log directories if missing."""
        for path in (self.cache_dir, self.output_dir, self.log_dir):
            path.mkdir(parents=True, exist_ok=True)


def _coerce(target_type: type, value: Any) -> Any:
    if value is None:
        return None
    if target_type is Path:
        return Path(value).expanduser()
    if target_type is tuple:
        return tuple(value)
    return target_type(value)


def load_config(path: Path | str | None = None) -> Config:
    """Load configuration from yaml + environment variables.

    Environment variables override yaml values. Recognized vars:
      SEC_USER_AGENT, CACHE_DIR, OUTPUT_DIR, LOG_LEVEL.
    """
    load_dotenv()
    cfg = Config()

    yaml_path = Path(path) if path else _DEFAULT_CONFIG_PATH
    if yaml_path.exists():
        with yaml_path.open("r", encoding="utf-8") as fh:
            data = yaml.safe_load(fh) or {}
        for key, value in data.items():
            if not hasattr(cfg, key):
                continue
            current = getattr(cfg, key)
            target_type = type(current) if current is not None else type(value)
            try:
                setattr(cfg, key, _coerce(target_type, value))
            except (TypeError, ValueError):
                setattr(cfg, key, value)

    env_overrides = {
        "sec_user_agent": os.environ.get("SEC_USER_AGENT"),
        "cache_dir": os.environ.get("CACHE_DIR"),
        "output_dir": os.environ.get("OUTPUT_DIR"),
        "log_level": os.environ.get("LOG_LEVEL"),
    }
    for key, value in env_overrides.items():
        if value:
            current = getattr(cfg, key)
            target_type = type(current) if current is not None else str
            setattr(cfg, key, _coerce(target_type, value))

    if cfg.cache_db.parent != cfg.cache_dir:
        cfg.cache_db = cfg.cache_dir / "analyzer.sqlite"

    cfg.ensure_dirs()
    return cfg
