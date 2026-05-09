"""Centralized logging setup."""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

_CONFIGURED = False


def setup_logging(log_dir: Path, level: str = "INFO") -> None:
    """Configure root logger with console + rotating file handler."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir.mkdir(parents=True, exist_ok=True)
    fmt = "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    formatter = logging.Formatter(fmt)

    root = logging.getLogger()
    root.setLevel(getattr(logging, level.upper(), logging.INFO))

    console = logging.StreamHandler()
    console.setFormatter(formatter)
    root.addHandler(console)

    file_handler = logging.handlers.RotatingFileHandler(
        log_dir / "analyzer.log", maxBytes=2_000_000, backupCount=3
    )
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Tame chatty third-party loggers.
    for noisy in ("urllib3", "yfinance", "matplotlib", "PIL"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
