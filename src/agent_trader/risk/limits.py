from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from ..utils.errors import RiskViolation


def _decimal(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RiskViolation(f"{label} must be a finite decimal.") from exc
    if not result.is_finite():
        raise RiskViolation(f"{label} must be a finite decimal.")
    return result


def _config_value(config: object, name: str, default: Any = None) -> Any:
    if isinstance(config, dict):
        return config.get(name, default)
    return getattr(config, name, default)


def _utc_date(value: date | datetime) -> date:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).date()
    if isinstance(value, date):
        return value
    raise RiskViolation("now must be a date or datetime.")


@dataclass
class RiskState:
    day: date
    start_equity: Decimal
    realized_pnl: Decimal = Decimal("0")
    consecutive_losses: int = 0
    open_positions: int = 0


class RiskManager:
    def __init__(self, risk_config: object, kill_switch: object | None) -> None:
        self.risk_config = risk_config
        self.kill_switch = kill_switch

    def _kill_switch_enabled(self) -> bool:
        return bool(_config_value(self.risk_config, "kill_switch_enabled", True))

    def _check_kill_switch(self) -> None:
        enabled = self._kill_switch_enabled()
        if self.kill_switch is None:
            if not enabled:
                return
            raise RiskViolation("Kill switch is enabled but unavailable.")
        if hasattr(self.kill_switch, "check"):
            self.kill_switch.check()
        elif enabled:
            raise RiskViolation("Kill switch is enabled but unavailable.")

    def _daily_loss_limit(self, state: RiskState) -> Decimal:
        start_equity = _decimal(state.start_equity, "start_equity")
        if start_equity <= 0:
            raise RiskViolation("start_equity must be greater than zero.")
        percent = _decimal(_config_value(self.risk_config, "max_daily_loss_pct"), "max_daily_loss_pct")
        if percent <= 0:
            raise RiskViolation("max_daily_loss_pct must be greater than zero.")
        return start_equity * percent / Decimal("100")

    def new_day_if_needed(self, state: RiskState, equity: object, now: date | datetime) -> RiskState:
        current_equity = _decimal(equity, "equity")
        if current_equity <= 0:
            raise RiskViolation("equity must be greater than zero.")
        current_day = _utc_date(now)
        if state.day != current_day:
            state.day = current_day
            state.start_equity = current_equity
            state.realized_pnl = Decimal("0")
            state.consecutive_losses = 0
        return state

    def record_trade_result(self, state: RiskState, pnl: object) -> None:
        result = _decimal(pnl, "pnl")
        if (isinstance(state.consecutive_losses, bool)
                or not isinstance(state.consecutive_losses, int)
                or state.consecutive_losses < 0):
            raise RiskViolation("consecutive_losses must be a non-negative integer.")
        state.realized_pnl = _decimal(state.realized_pnl, "realized_pnl") + result
        if result < 0:
            state.consecutive_losses += 1
        elif result > 0:
            state.consecutive_losses = 0

        if not self._kill_switch_enabled():
            return
        daily_limit = self._daily_loss_limit(state)
        daily_loss = max(-state.realized_pnl, Decimal("0"))
        max_losses = _config_value(self.risk_config, "max_consecutive_losses")
        if isinstance(max_losses, bool) or not isinstance(max_losses, int) or max_losses < 1:
            raise RiskViolation("max_consecutive_losses must be a positive integer.")
        if daily_loss >= daily_limit:
            self._engage("daily realized loss limit reached")
        elif state.consecutive_losses >= max_losses:
            self._engage("maximum consecutive losses reached")

    def _engage(self, reason: str) -> None:
        if self.kill_switch is None or not hasattr(self.kill_switch, "engage"):
            raise RiskViolation("Kill switch is enabled but unavailable.")
        self.kill_switch.engage(reason)

    def check_new_trade(self, state: RiskState) -> None:
        self._check_kill_switch()
        maximum = _config_value(self.risk_config, "max_open_positions")
        if isinstance(maximum, bool) or not isinstance(maximum, int) or maximum < 1:
            raise RiskViolation("max_open_positions must be a positive integer.")
        if (isinstance(state.open_positions, bool)
                or not isinstance(state.open_positions, int)
                or state.open_positions < 0):
            raise RiskViolation("open_positions must be a non-negative integer.")
        if state.open_positions >= maximum:
            raise RiskViolation("Maximum open positions reached.")
        daily_loss = max(-_decimal(state.realized_pnl, "realized_pnl"), Decimal("0"))
        if daily_loss >= self._daily_loss_limit(state):
            raise RiskViolation("Daily realized loss limit exceeded.")
