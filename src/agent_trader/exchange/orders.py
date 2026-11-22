from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Literal, Mapping
from ..utils.errors import RiskViolation


@dataclass(frozen=True)
class OrderRequest:
    symbol: str
    side: Literal["BUY", "SELL"]
    order_type: str
    quantity: Decimal | str | float
    price: Decimal | str | float | None = None
    stop_price: Decimal | str | float | None = None
    reduce_only: bool = False


def _decimal(value: object, label: str) -> Decimal:
    try:
        result = Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError) as exc:
        raise RiskViolation(f"Order {label} must be a valid decimal.") from exc
    if not result.is_finite():
        raise RiskViolation(f"Order {label} must be finite.")
    return result


def _aligned(value: Decimal, step: Decimal) -> bool:
    if step <= 0:
        raise RiskViolation("Exchange filters must contain positive increments.")
    return value % step == 0


def validate_order(request: OrderRequest, filters: Mapping[str, object]) -> None:
    if not request.symbol or request.side not in ("BUY", "SELL"):
        raise RiskViolation("Order requires a symbol and BUY or SELL side.")
    if request.order_type not in ("MARKET", "LIMIT", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"):
        raise RiskViolation("Unsupported order type.")
    quantity = _decimal(request.quantity, "quantity")
    step = _decimal(filters.get("step_size", "0"), "step_size")
    minimum = _decimal(filters.get("min_qty", "0"), "min_qty")
    if quantity <= 0 or quantity < minimum or not _aligned(quantity, step):
        raise RiskViolation("Order quantity is invalid or violates minimum/step size.")
    tick = _decimal(filters.get("tick_size", "0"), "tick_size")
    for label, raw in (("price", request.price), ("stop price", request.stop_price)):
        if raw is not None:
            price = _decimal(raw, label)
            if price <= 0 or not _aligned(price, tick):
                raise RiskViolation(f"Order {label} is invalid or not aligned to tick size.")
    notional_min = _decimal(filters.get("min_notional", "0"), "min_notional")
    if notional_min > 0:
        reference = request.price if request.price is not None else request.stop_price
        if reference is None:
            raise RiskViolation("A reference price is required to validate minimum notional.")
        if quantity * _decimal(reference, "price") < notional_min:
            raise RiskViolation("Order notional is below the exchange minimum.")


def build_order_params(request: OrderRequest) -> dict[str, str]:
    params = {"symbol": request.symbol, "side": request.side, "type": request.order_type,
              "quantity": format(_decimal(request.quantity, "quantity"), "f")}
    if request.price is not None:
        params["price"] = format(_decimal(request.price, "price"), "f")
    if request.stop_price is not None:
        params["stopPrice"] = format(_decimal(request.stop_price, "stop price"), "f")
    if request.order_type in ("LIMIT", "STOP_LOSS_LIMIT", "TAKE_PROFIT_LIMIT"):
        params["timeInForce"] = "GTC"
    if request.reduce_only:
        params["reduceOnly"] = "true"
    return params
