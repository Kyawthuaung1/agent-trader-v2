import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from types import SimpleNamespace

from agent_trader.risk.kill_switch import KillSwitch
from agent_trader.risk.limits import RiskManager, RiskState
from agent_trader.utils.errors import RiskViolation


def make_config(**overrides: object) -> SimpleNamespace:
    values = {
        "max_daily_loss_pct": Decimal("5"),
        "max_consecutive_losses": 3,
        "max_open_positions": 2,
        "kill_switch_enabled": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


class TestRiskLimits(unittest.TestCase):
    def test_new_utc_day_resets_daily_state(self) -> None:
        manager = RiskManager(make_config(), None)
        state = RiskState(
            day=date(2025, 1, 1), start_equity=Decimal("1000"),
            realized_pnl=Decimal("-12"), consecutive_losses=2, open_positions=1
        )
        now = datetime(2025, 1, 2, 3, tzinfo=timezone(timedelta(hours=2)))
        returned = manager.new_day_if_needed(state, Decimal("975"), now)
        self.assertIs(returned, state)
        self.assertEqual(state.day, date(2025, 1, 2))
        self.assertEqual(state.start_equity, Decimal("975"))
        self.assertEqual(state.realized_pnl, Decimal("0"))
        self.assertEqual(state.consecutive_losses, 0)
        self.assertEqual(state.open_positions, 1)

    def test_daily_loss_and_consecutive_loss_engage_switch(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            daily_switch = KillSwitch(Path(directory) / "daily.json")
            daily_manager = RiskManager(make_config(), daily_switch)
            daily_state = RiskState(date(2025, 1, 1), Decimal("1000"))
            daily_manager.record_trade_result(daily_state, Decimal("-50"))
            self.assertTrue(daily_switch.is_engaged())
            with self.assertRaises(RiskViolation):
                daily_manager.check_new_trade(daily_state)

            loss_switch = KillSwitch(Path(directory) / "streak.json")
            loss_manager = RiskManager(
                make_config(max_consecutive_losses=2), loss_switch
            )
            loss_state = RiskState(date(2025, 1, 1), Decimal("1000"))
            loss_manager.record_trade_result(loss_state, Decimal("-1"))
            self.assertFalse(loss_switch.is_engaged())
            loss_manager.record_trade_result(loss_state, Decimal("-1"))
            self.assertTrue(loss_switch.is_engaged())
            self.assertEqual(loss_state.consecutive_losses, 2)

    def test_win_resets_loss_streak_and_open_position_limit_is_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            switch = KillSwitch(Path(directory) / "switch.json")
            manager = RiskManager(make_config(), switch)
            state = RiskState(date(2025, 1, 1), Decimal("1000"))
            manager.record_trade_result(state, Decimal("-1"))
            manager.record_trade_result(state, Decimal("2"))
            self.assertEqual(state.consecutive_losses, 0)
            manager.check_new_trade(state)
            state.open_positions = 2
            with self.assertRaises(RiskViolation):
                manager.check_new_trade(state)

    def test_kill_switch_disabled_skips_automatic_switch_engagement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            switch = KillSwitch(Path(directory) / "switch.json")
            manager = RiskManager(
                make_config(kill_switch_enabled=False, max_daily_loss_pct=Decimal("10")),
                switch,
            )
            state = RiskState(date(2025, 1, 1), Decimal("1000"))
            manager.record_trade_result(state, Decimal("-50"))
            self.assertFalse(switch.is_engaged())
            manager.check_new_trade(state)


if __name__ == "__main__":
    unittest.main()
