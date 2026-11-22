from __future__ import annotations

from abc import ABC, abstractmethod
from functools import wraps

from ..data.candles import Candle
from ..utils.errors import ConfigError
from .signals import MarketSnapshot, Signal, SignalType


class Strategy(ABC):
    """Pure strategy interface with closed-candle and warm-up guards."""

    name: str = ""

    def __init__(self, params: dict) -> None:
        if not isinstance(params, dict):
            raise ConfigError("Strategy params must be a dictionary.")
        self.params = dict(params)

    def __init_subclass__(cls, **kwargs: object) -> None:
        super().__init_subclass__(**kwargs)
        implementation = cls.__dict__.get("generate")
        if implementation is None or getattr(implementation, "_strategy_guarded", False):
            return

        @wraps(implementation)
        def guarded_generate(self: Strategy, snapshot: MarketSnapshot) -> Signal:
            if not isinstance(snapshot, MarketSnapshot):
                raise ConfigError("Strategy.generate requires a MarketSnapshot.")
            closed: dict[str, list[Candle]] = {}
            try:
                for timeframe, candles in snapshot.candles.items():
                    closed[timeframe] = [
                        candle for candle in candles if candle.close_time_ms < snapshot.now_ms
                    ]
            except (AttributeError, TypeError) as exc:
                raise ConfigError("Snapshot candles must contain valid Candle sequences.") from exc

            requirements = self.required_candles()
            if not isinstance(requirements, dict):
                raise ConfigError("required_candles() must return a timeframe-to-count dictionary.")
            for timeframe, count in requirements.items():
                if isinstance(count, bool) or not isinstance(count, int) or count < 0:
                    raise ConfigError("Required candle counts must be non-negative integers.")
                available = len(closed.get(timeframe, []))
                if available < count:
                    return Signal(
                        symbol=snapshot.symbol,
                        type=SignalType.HOLD,
                        reason=f"Insufficient closed {timeframe} candles: need {count}, got {available}.",
                        timestamp_ms=snapshot.now_ms,
                        meta={
                            "timeframe": timeframe,
                            "required": count,
                            "available": available,
                        },
                    )

            clean_snapshot = MarketSnapshot(
                symbol=snapshot.symbol, candles=closed, now_ms=snapshot.now_ms
            )
            return implementation(self, clean_snapshot)

        guarded_generate._strategy_guarded = True  # type: ignore[attr-defined]
        setattr(cls, "generate", guarded_generate)

    @abstractmethod
    def required_candles(self) -> dict[str, int]:
        """Return the minimum closed-candle count required for each timeframe."""
        raise NotImplementedError

    @abstractmethod
    def generate(self, snapshot: MarketSnapshot) -> Signal:
        """Generate a signal from a closed-candle snapshot without side effects."""
        raise NotImplementedError
