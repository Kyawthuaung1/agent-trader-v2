import unittest

from agent_trader.data.candles import Candle
from agent_trader.strategy.base import Strategy
from agent_trader.strategy.registry import get_strategy, list_strategies, register
from agent_trader.strategy.signals import MarketSnapshot, Signal, SignalType
from agent_trader.utils.errors import ConfigError


def make_candle(close_time_ms: int) -> Candle:
    return Candle(
        open_time_ms=max(0, close_time_ms - 10), open=100.0, high=101.0,
        low=99.0, close=100.0, volume=1.0, close_time_ms=close_time_ms
    )


@register("unit_dummy")
class DummyStrategy(Strategy):
    def required_candles(self) -> dict[str, int]:
        return {"4h": 2, "15m": 3}

    def generate(self, snapshot: MarketSnapshot) -> Signal:
        return Signal(
            symbol=snapshot.symbol, type=SignalType.ENTER_LONG,
            reason="dummy strategy", timestamp_ms=snapshot.now_ms,
            entry_price=100.0, stop_price=90.0, meta={"tested": True}
        )


class TestStrategy(unittest.TestCase):
    def test_registry_instantiates_and_lists_strategy(self) -> None:
        strategy = get_strategy("unit_dummy", {"period": 3})
        self.assertIsInstance(strategy, DummyStrategy)
        self.assertEqual(strategy.params, {"period": 3})
        self.assertEqual(strategy.name, "unit_dummy")
        self.assertIn("unit_dummy", list_strategies())
        with self.assertRaises(ConfigError):
            get_strategy("not_registered", {})

    def test_dummy_strategy_holds_until_all_timeframes_are_closed_and_ready(self) -> None:
        strategy = get_strategy("unit_dummy", {})
        now_ms = 100
        too_few = MarketSnapshot(
            symbol="BTCUSDT",
            candles={
                "4h": [make_candle(80), make_candle(90)],
                "15m": [make_candle(70), make_candle(80), make_candle(now_ms)],
            },
            now_ms=now_ms,
        )
        signal = strategy.generate(too_few)
        self.assertEqual(signal.type, SignalType.HOLD)
        self.assertEqual(signal.meta["timeframe"], "15m")
        self.assertEqual(signal.meta["available"], 2)

        ready = MarketSnapshot(
            symbol="BTCUSDT",
            candles={
                "4h": [make_candle(80), make_candle(90)],
                "15m": [make_candle(70), make_candle(80), make_candle(90)],
            },
            now_ms=now_ms,
        )
        generated = strategy.generate(ready)
        self.assertEqual(generated.type, SignalType.ENTER_LONG)
        self.assertEqual(generated.meta, {"tested": True})


if __name__ == "__main__":
    unittest.main()
