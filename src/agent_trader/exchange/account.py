from __future__ import annotations

from decimal import Decimal
from ..utils.errors import ExchangeError
from .binance_client import BinanceClient


def get_balances(client: BinanceClient) -> list[dict[str, str]]:
    """Read and normalize either spot or futures balances."""
    futures = client.settings.exchange.market_type == "futures"
    response = client.signed_get("/fapi/v2/balance" if futures else "/api/v3/account")
    rows = response if futures else response.get("balances") if isinstance(response, dict) else None
    if not isinstance(rows, list):
        raise ExchangeError("Binance balance response is invalid.")
    balances: list[dict[str, str]] = []
    try:
        for row in rows:
            if futures:
                total = Decimal(str(row.get("balance", "0")))
                free = Decimal(str(row.get("availableBalance", "0")))
                locked = max(total-free, Decimal("0"))
            else:
                free = Decimal(str(row.get("free", "0")))
                locked = Decimal(str(row.get("locked", "0")))
                total = free + locked
            balances.append({"asset": str(row["asset"]), "free": str(free),
                             "locked": str(locked), "total": str(total)})
    except (TypeError, KeyError, ArithmeticError, ValueError) as exc:
        raise ExchangeError("Binance balance response is invalid.") from exc
    return balances


def get_open_orders(client: BinanceClient, symbol: str) -> list[dict[str, object]]:
    path = "/fapi/v1/openOrders" if client.settings.exchange.market_type == "futures" else "/api/v3/openOrders"
    response = client.signed_get(path, {"symbol": symbol})
    if not isinstance(response, list) or any(not isinstance(order, dict) for order in response):
        raise ExchangeError("Binance open-orders response is invalid.")
    return response
