"""
Structured Logging fuer Rainer Build.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path


class RainerLogger:
    LOG_LEVELS = {
        "debug": logging.DEBUG,
        "info": logging.INFO,
        "warning": logging.WARNING,
        "error": logging.ERROR,
        "critical": logging.CRITICAL,
    }

    def __init__(self, name: str = "rainer_build", level: str = "info"):
        self.logger = logging.getLogger(name)
        if self.logger.handlers:
            return
        self.logger.setLevel(self.LOG_LEVELS.get(level, logging.INFO))

        log_dir = Path(__file__).resolve().parent.parent / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / f"rainer_build_{datetime.now().strftime('%Y%m%d')}.log"

        fh = logging.FileHandler(log_file, encoding="utf-8")
        ch = logging.StreamHandler()
        fh.setLevel(self.logger.level)
        ch.setLevel(self.logger.level)

        fmt = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        fh.setFormatter(fmt)
        ch.setFormatter(fmt)

        self.logger.addHandler(fh)
        self.logger.addHandler(ch)

    def log_api_call(self, endpoint: str, method: str, status: int, duration: float):
        self.logger.info(f"API: {method} {endpoint} -> {status} ({duration:.3f}s)")

    def log_file_operation(self, operation: str, filepath: str, success: bool):
        marker = "OK" if success else "ERR"
        self.logger.info(f"FILE: {marker} {operation} {filepath}")

    def log_error_with_context(self, error: str, context: dict):
        try:
            ctx = json.dumps(context, ensure_ascii=True)
        except Exception:
            ctx = "{}"
        self.logger.error(f"ERROR: {error} | Context: {ctx}")

    def log_performance(self, operation: str, duration: float):
        if duration > 1.0:
            self.logger.warning(f"SLOW: {operation} took {duration:.3f}s")
