from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum

from ..data.candles import Candle


class SignalType(str, Enum):
    ENTER_LONG = "ENTER_LONG"
    ENTER_SHORT = "ENTER_SHORT"
    EXIT = "EXIT"
    HOLD = "HOLD"


@dataclass(frozen=True)
class Signal:
    symbol: str
    type: SignalType
    reason: str
    timestamp_ms: int
    entry_price: float | None = None
    stop_price: float | None = None
    take_profit: float | None = None
    meta: dict = field(default_factory=dict)


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    candles: dict[str, list[Candle]]
    now_ms: int
