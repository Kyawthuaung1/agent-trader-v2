from __future__ import annotations

import re
from datetime import datetime, timezone

from .errors import ConfigError

_TIMEFRAME_UNITS = {
    "s": 1,
    "m": 60,
    "h": 60 * 60,
    "d": 24 * 60 * 60,
    "w": 7 * 24 * 60 * 60,
}
_TIMEFRAME_PATTERN = re.compile(r"([1-9][0-9]*)([smhdw])")


def utc_now() -> datetime:
    """Return the current timezone-aware UTC datetime."""
    return datetime.now(timezone.utc)


def to_ms(value: datetime) -> int:
    """Convert a datetime to Unix time in milliseconds.

    Naive datetimes are interpreted as UTC. Aware datetimes are converted to UTC.
    """
    if not isinstance(value, datetime):
        raise TypeError("value must be a datetime")
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return int(value.astimezone(timezone.utc).timestamp() * 1000)


def from_ms(value: int) -> datetime:
    """Convert Unix time in milliseconds to a timezone-aware UTC datetime."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("value must be an integer number of milliseconds")
    return datetime.fromtimestamp(value / 1000, tz=timezone.utc)


def timeframe_to_seconds(timeframe: str) -> int:
    """Convert a positive timeframe such as ``15m`` or ``1d`` to seconds."""
    if not isinstance(timeframe, str):
        raise ConfigError("Timeframe must be a string such as '15m' or '1h'.")
    match = _TIMEFRAME_PATTERN.fullmatch(timeframe)
    if match is None:
        raise ConfigError(
            f"Invalid timeframe {timeframe!r}; use a positive integer followed by s, m, h, d, or w."
        )
    amount, unit = match.groups()
    return int(amount) * _TIMEFRAME_UNITS[unit]
