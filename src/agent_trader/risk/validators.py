from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal, Mapping

from ..exchange.orders import OrderRequest, validate_order
from ..strategy.signals import Signal, SignalType
from ..utils.errors import RiskViolation
from .limits import RiskManager, RiskState
from .position_sizing import calc_position_size

MAX_ENTRY_DEVIATION_PCT = Decimal("1.0")


@dataclass(frozen=True)
class TradePlan:
    symbol: str
    side: Literal["BUY", "SELL"]
    quantity: Decimal
    entry_price: Decimal
    stop_price: Decimal
    take_profit: Decimal | None
    risk_amount: Decimal


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise RiskViolation(f"{label} must be a finite decimal.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RiskViolation(f"{label} must be a finite decimal.") from exc
    if not result.is_finite():
        raise RiskViolation(f"{label} must be a finite decimal.")
    return result


def validate_signal(
    signal: Signal,
    settings: object,
    risk_manager: RiskManager,
    state: RiskState,
    equity: object,
    last_price: object,
    filters: Mapping[str, object],
) -> TradePlan:
    """Validate a proposed entry and return a Decimal-only, non-mutating plan."""
    try:
        risk_config = settings.risk
        kill_enabled = bool(getattr(risk_config, "kill_switch_enabled", True))
        switch = getattr(risk_manager, "kill_switch", None)
        if switch is not None and hasattr(switch, "check"):
            switch.check()
        elif kill_enabled:
            raise RiskViolation("Kill switch is enabled but unavailable.")
        risk_manager.check_new_trade(state)

        if signal.type not in (SignalType.ENTER_LONG, SignalType.ENTER_SHORT):
            raise RiskViolation("Only ENTER_LONG or ENTER_SHORT signals can create a trade plan.")
        entry = _decimal(signal.entry_price, "entry_price")
        if entry <= 0:
            raise RiskViolation("Entry price must be greater than zero.")

        stop_required = bool(getattr(risk_config, "stop_loss_required", True))
        if signal.stop_price is None and stop_required:
            raise RiskViolation("A stop price is required by the risk policy.")
        if signal.stop_price is None:
            raise RiskViolation("A stop price is needed to calculate a risk-based position size.")
        stop = _decimal(signal.stop_price, "stop_price")
        if stop <= 0 or stop == entry:
            raise RiskViolation("Stop price must be positive and different from entry.")
        if signal.type == SignalType.ENTER_LONG and stop >= entry:
            raise RiskViolation("A long stop price must be below entry.")
        if signal.type == SignalType.ENTER_SHORT and stop <= entry:
            raise RiskViolation("A short stop price must be above entry.")

        current_price = _decimal(last_price, "last_price")
        if current_price <= 0:
            raise RiskViolation("Last price must be greater than zero.")
        if abs(entry - current_price) / current_price * Decimal("100") > MAX_ENTRY_DEVIATION_PCT:
            raise RiskViolation("Entry price is more than 1.0% away from the last price.")

        market_type = str(settings.exchange.market_type)
        if market_type not in ("spot", "futures"):
            raise RiskViolation("Unsupported market type.")
        if signal.type == SignalType.ENTER_SHORT and market_type == "spot":
            raise RiskViolation("Short entries are not allowed for spot markets.")

        take_profit = None if signal.take_profit is None else _decimal(signal.take_profit, "take_profit")
        if take_profit is not None:
            if take_profit <= 0:
                raise RiskViolation("Take-profit price must be greater than zero.")
            if signal.type == SignalType.ENTER_LONG and take_profit <= entry:
                raise RiskViolation("A long take-profit price must be above entry.")
            if signal.type == SignalType.ENTER_SHORT and take_profit >= entry:
                raise RiskViolation("A short take-profit price must be below entry.")

        quantity = calc_position_size(
            equity=equity,
            risk_pct=risk_config.max_risk_per_trade_pct,
            entry=entry,
            stop=stop,
            filters=filters,
            max_leverage=risk_config.max_leverage,
            market_type=market_type,
        )
        side: Literal["BUY", "SELL"] = (
            "BUY" if signal.type == SignalType.ENTER_LONG else "SELL"
        )
        order = OrderRequest(
            symbol=signal.symbol, side=side, order_type="LIMIT",
            quantity=quantity, price=entry, stop_price=stop, reduce_only=False
        )
        validate_order(order, filters)
        return TradePlan(
            symbol=signal.symbol, side=side, quantity=quantity, entry_price=entry,
            stop_price=stop, take_profit=take_profit,
            risk_amount=quantity * abs(entry - stop),
        )
    except RiskViolation:
        raise
    except Exception as exc:
        raise RiskViolation("Signal or risk configuration is invalid.") from exc
