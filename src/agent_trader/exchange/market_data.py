from __future__ import annotations

from ..data.candles import Candle, parse_klines
from ..utils.errors import ExchangeError
from .binance_client import BinanceClient


def _futures(client: BinanceClient) -> bool:
    return str(client.settings.exchange.market_type) == "futures"


def get_server_time(client: BinanceClient) -> int:
    response = client.public_get("/fapi/v1/time" if _futures(client) else "/api/v3/time")
    try:
        return int(response["serverTime"])
    except (TypeError, KeyError, ValueError) as exc:
        raise ExchangeError("Binance server-time response is invalid.") from exc


def get_klines(client: BinanceClient, symbol: str, interval: str, limit: int) -> list[Candle]:
    path = "/fapi/v1/klines" if _futures(client) else "/api/v3/klines"
    response = client.public_get(path, {"symbol": symbol, "interval": interval, "limit": limit})
    if not isinstance(response, list):
        raise ExchangeError("Binance kline response is not a list.")
    try:
        return parse_klines(response)
    except (TypeError, ValueError) as exc:
        raise ExchangeError("Binance kline response contains invalid candle data.") from exc


def get_last_price(client: BinanceClient, symbol: str) -> float:
    path = "/fapi/v1/ticker/price" if _futures(client) else "/api/v3/ticker/price"
    response = client.public_get(path, {"symbol": symbol})
    try:
        return float(response["price"])
    except (TypeError, KeyError, ValueError) as exc:
        raise ExchangeError("Binance ticker response is invalid.") from exc


def get_symbol_filters(client: BinanceClient, symbol: str) -> dict[str, str]:
    path = "/fapi/v1/exchangeInfo" if _futures(client) else "/api/v3/exchangeInfo"
    response = client.public_get(path, {"symbol": symbol})
    try:
        item = next(entry for entry in response["symbols"] if entry["symbol"] == symbol)
        filters = {entry["filterType"]: entry for entry in item["filters"]}
        lot, price = filters["LOT_SIZE"], filters["PRICE_FILTER"]
        notional = filters.get("NOTIONAL") or filters.get("MIN_NOTIONAL") or {}
        return {
            "tick_size": str(price["tickSize"]),
            "step_size": str(lot["stepSize"]),
            "min_notional": str(notional.get("minNotional", notional.get("notional", "0"))),
            "min_qty": str(lot["minQty"]),
        }
    except (TypeError, KeyError, StopIteration, ValueError) as exc:
        raise ExchangeError(f"No usable trading filters found for symbol {symbol}.") from exc
