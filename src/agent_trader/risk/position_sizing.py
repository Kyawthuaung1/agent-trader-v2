from __future__ import annotations

from decimal import Decimal, InvalidOperation, ROUND_DOWN
from collections.abc import Mapping

from ..utils.errors import RiskViolation


def _decimal(value: object, label: str) -> Decimal:
    if isinstance(value, bool):
        raise RiskViolation(f"{label} must be a positive finite number.")
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RiskViolation(f"{label} must be a positive finite number.") from exc
    if not result.is_finite() or result <= 0:
        raise RiskViolation(f"{label} must be greater than zero.")
    return result


def calc_position_size(
    equity: Decimal | str | int | float,
    risk_pct: Decimal | str | int | float,
    entry: Decimal | str | int | float,
    stop: Decimal | str | int | float,
    filters: Mapping[str, object],
    max_leverage: Decimal | str | int | float,
    market_type: str,
) -> Decimal:
    """Calculate risk-based size, enforce leverage/minimums, and round down."""
    account_equity = _decimal(equity, "equity")
    risk_percent = _decimal(risk_pct, "risk_pct")
    entry_price = _decimal(entry, "entry")
    stop_price = _decimal(stop, "stop")
    leverage = _decimal(max_leverage, "max_leverage")
    if not isinstance(filters, Mapping):
        raise RiskViolation("Exchange filters must be a mapping.")
    step_size = _decimal(filters.get("step_size"), "step_size")
    min_qty = _decimal(filters.get("min_qty"), "min_qty")
    min_notional = _decimal(filters.get("min_notional"), "min_notional")

    if market_type not in {"spot", "futures"}:
        raise RiskViolation("market_type must be spot or futures.")
    if entry_price == stop_price:
        raise RiskViolation("Entry and stop prices must be different.")

    risk_budget = account_equity * risk_percent / Decimal("100")
    quantity = risk_budget / abs(entry_price - stop_price)
    effective_leverage = Decimal("1") if market_type == "spot" else leverage
    leverage_cap = account_equity * effective_leverage / entry_price
    quantity = min(quantity, leverage_cap)
    steps = (quantity / step_size).to_integral_value(rounding=ROUND_DOWN)
    quantity = steps * step_size

    if quantity < min_qty:
        raise RiskViolation("Calculated quantity is below the exchange minimum quantity.")
    notional = quantity * entry_price
    if notional < min_notional:
        raise RiskViolation("Calculated notional is below the exchange minimum notional.")
    return quantity
