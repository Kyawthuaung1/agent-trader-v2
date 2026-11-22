from __future__ import annotations

from collections.abc import Sequence
from ..utils.errors import ConfigError


def _validate_period(period: int) -> None:
    if isinstance(period, bool) or not isinstance(period, int) or period < 1:
        raise ConfigError("Indicator period must be an integer greater than or equal to 1.")


def sma(values: Sequence[float], period: int) -> list[float | None]:
    _validate_period(period)
    result: list[float | None] = [None] * len(values)
    total = 0.0
    for i, value in enumerate(values):
        total += float(value)
        if i >= period:
            total -= float(values[i-period])
        if i >= period-1:
            result[i] = total / period
    return result


def ema(values: Sequence[float], period: int) -> list[float | None]:
    _validate_period(period)
    result: list[float | None] = [None] * len(values)
    if len(values) < period:
        return result
    current = sum(map(float, values[:period])) / period
    result[period-1] = current
    alpha = 2.0 / (period + 1)
    for i in range(period, len(values)):
        current = (float(values[i]) - current) * alpha + current
        result[i] = current
    return result


def rsi(values: Sequence[float], period: int = 14) -> list[float | None]:
    _validate_period(period)
    result: list[float | None] = [None] * len(values)
    if len(values) <= period:
        return result
    changes = [float(values[i])-float(values[i-1]) for i in range(1, len(values))]
    gains = [max(change, 0.0) for change in changes]
    losses = [max(-change, 0.0) for change in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    def value(gain: float, loss: float) -> float:
        if loss == 0.0:
            return 100.0 if gain > 0.0 else 50.0
        if gain == 0.0:
            return 0.0
        return 100.0 - 100.0 / (1.0 + gain / loss)

    result[period] = value(avg_gain, avg_loss)
    for i in range(period+1, len(values)):
        change = changes[i-1]
        avg_gain = (avg_gain*(period-1) + max(change, 0.0)) / period
        avg_loss = (avg_loss*(period-1) + max(-change, 0.0)) / period
        result[i] = value(avg_gain, avg_loss)
    return result


def atr(highs: Sequence[float], lows: Sequence[float], closes: Sequence[float],
        period: int = 14) -> list[float | None]:
    _validate_period(period)
    if not (len(highs) == len(lows) == len(closes)):
        raise ConfigError("High, low, and close series must have equal lengths.")
    result: list[float | None] = [None] * len(highs)
    if len(highs) < period:
        return result
    ranges: list[float] = []
    for i, (high, low) in enumerate(zip(highs, lows)):
        high, low = float(high), float(low)
        if i == 0:
            ranges.append(high-low)
        else:
            previous = float(closes[i-1])
            ranges.append(max(high-low, abs(high-previous), abs(low-previous)))
    current = sum(ranges[:period]) / period
    result[period-1] = current
    for i in range(period, len(ranges)):
        current = (current*(period-1) + ranges[i]) / period
        result[i] = current
    return result
