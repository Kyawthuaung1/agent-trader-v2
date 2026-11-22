import tempfile
import unittest
from datetime import date
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from agent_trader.risk.kill_switch import KillSwitch
from agent_trader.risk.limits import RiskManager, RiskState
from agent_trader.risk.validators import TradePlan, validate_signal
from agent_trader.strategy.signals import Signal, SignalType
from agent_trader.utils.errors import RiskViolation


def make_settings(market_type: str = "spot") -> SimpleNamespace:
    return SimpleNamespace(
        exchange=SimpleNamespace(market_type=market_type),
        risk=SimpleNamespace(
            kill_switch_enabled=True, stop_loss_required=True,
            max_risk_per_trade_pct=Decimal("1"), max_leverage=Decimal("3"),
            max_daily_loss_pct=Decimal("5"), max_consecutive_losses=3,
            max_open_positions=2,
        ),
    )


def make_signal(
    signal_type: SignalType = SignalType.ENTER_LONG,
    entry: float | None = 100.0, stop: float | None = 90.0,
    take_profit: float | None = 120.0,
) -> Signal:
    return Signal(
        symbol="BTCUSDT", type=signal_type, reason="unit test",
        timestamp_ms=1_000, entry_price=entry, stop_price=stop,
        take_profit=take_profit,
    )


class TestSignalValidator(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.switch = KillSwitch(Path(self.temp.name) / "switch.json")
        self.settings = make_settings()
        self.manager = RiskManager(self.settings.risk, self.switch)
        self.state = RiskState(date(2025, 1, 1), Decimal("1000"))
        self.filters = {
            "step_size": "0.01", "min_qty": "0.01",
            "tick_size": "0.1", "min_notional": "5",
        }

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_valid_long_returns_decimal_plan_without_mutating_filters(self) -> None:
        original_filters = dict(self.filters)
        plan = validate_signal(
            make_signal(), self.settings, self.manager, self.state,
            equity=Decimal("1000"), last_price=Decimal("100"),
            filters=self.filters,
        )
        self.assertIsInstance(plan, TradePlan)
        self.assertEqual(plan.side, "BUY")
        self.assertEqual(plan.quantity, Decimal("1"))
        self.assertEqual(plan.entry_price, Decimal("100.0"))
        self.assertEqual(plan.risk_amount, Decimal("10.0"))
        self.assertEqual(self.filters, original_filters)

    def test_kill_switch_spot_short_stop_and_entry_deviation_are_rejected(self) -> None:
        self.switch.engage("test")
        with self.assertRaises(RiskViolation):
            validate_signal(
                make_signal(), self.settings, self.manager, self.state,
                Decimal("1000"), Decimal("100"), self.filters
            )
        self.switch.reset()

        with self.assertRaises(RiskViolation):
            validate_signal(
                make_signal(SignalType.ENTER_SHORT, entry=100.0, stop=110.0),
                self.settings, self.manager, self.state, Decimal("1000"),
                Decimal("100"), self.filters
            )
        with self.assertRaises(RiskViolation):
            validate_signal(
                make_signal(stop=None), self.settings, self.manager, self.state,
                Decimal("1000"), Decimal("100"), self.filters
            )
        with self.assertRaises(RiskViolation):
            validate_signal(
                make_signal(stop=101.0), self.settings, self.manager, self.state,
                Decimal("1000"), Decimal("100"), self.filters
            )
        with self.assertRaises(RiskViolation):
            validate_signal(
                make_signal(entry=102.0, stop=90.0), self.settings, self.manager,
                self.state, Decimal("1000"), Decimal("100"), self.filters
            )

    def test_order_tick_filter_is_enforced_after_sizing(self) -> None:
        bad_tick_filters = dict(self.filters, tick_size="3")
        with self.assertRaises(RiskViolation):
            validate_signal(
                make_signal(), self.settings, self.manager, self.state,
                Decimal("1000"), Decimal("100"), bad_tick_filters
            )

    def test_futures_short_with_correct_stop_is_allowed(self) -> None:
        self.settings = make_settings("futures")
        self.manager = RiskManager(self.settings.risk, self.switch)
        plan = validate_signal(
            make_signal(SignalType.ENTER_SHORT, entry=100.0, stop=110.0, take_profit=80.0),
            self.settings, self.manager, self.state, Decimal("1000"),
            Decimal("100"), self.filters
        )
        self.assertEqual(plan.side, "SELL")
        self.assertEqual(plan.stop_price, Decimal("110.0"))


if __name__ == "__main__":
    unittest.main()
