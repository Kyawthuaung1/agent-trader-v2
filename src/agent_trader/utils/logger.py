from __future__ import annotations

import logging
import os
import time as time_module
from logging.handlers import RotatingFileHandler
from pathlib import Path

_SECRET_ENV_VARS = (
    "BINANCE_API_KEY",
    "BINANCE_API_SECRET",
    "LLM_API_KEY",
    "TELEGRAM_BOT_TOKEN",
)
_LOG_FORMAT = "%(asctime)sZ %(levelname)s %(name)s: %(message)s"


class _SecretMaskingFormatter(logging.Formatter):
    """Format log records in UTC and redact secrets from the complete output."""

    converter = time_module.gmtime

    def format(self, record: logging.LogRecord) -> str:
        rendered = super().format(record)
        secrets = sorted(
            (os.environ[name] for name in _SECRET_ENV_VARS if os.environ.get(name)),
            key=len,
            reverse=True,
        )
        for secret in secrets:
            rendered = rendered.replace(secret, "[REDACTED]")
        return rendered


def _project_root() -> Path:
    return Path(__file__).resolve().parents[3]


def get_logger(name: str) -> logging.Logger:
    """Return a logger with UTC console and rotating ``logs/agent.log`` output."""
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    if not logger.handlers:
        log_path = _project_root() / "logs" / "agent.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        formatter = _SecretMaskingFormatter(_LOG_FORMAT, datefmt="%Y-%m-%dT%H:%M:%S")

        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

        file_handler = RotatingFileHandler(
            log_path,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger
