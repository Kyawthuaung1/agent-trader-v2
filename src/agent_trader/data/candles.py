from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


@dataclass(frozen=True)
class Candle:
    open_time_ms: int
    open: float
    high: float
    low: float
    close: float
    volume: float
    close_time_ms: int


def parse_klines(raw: Sequence[Sequence[object]]) -> list[Candle]:
    candles: list[Candle] = []
    for index, row in enumerate(raw):
        if len(row) < 7:
            raise ValueError(f"Kline row {index} must contain at least seven fields.")
        try:
            candles.append(Candle(int(row[0]), float(row[1]), float(row[2]), float(row[3]),
                                  float(row[4]), float(row[5]), int(row[6])))
        except (TypeError, ValueError, OverflowError) as exc:
            raise ValueError(f"Kline row {index} contains invalid values.") from exc
    return candles


def drop_unclosed(candles: Sequence[Candle], now_ms: int) -> list[Candle]:
    return [candle for candle in candles if candle.close_time_ms < now_ms]
