from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
from collections.abc import Callable, Mapping
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from ..utils.errors import ConfigError, ExchangeError, LiveTradingNotAllowed

HttpCallable = Callable[[str, str, dict[str, str], float], tuple[int, str]]
_BASE_URLS = {
    ("spot", True): "https://testnet.binance.vision",
    ("spot", False): "https://api.binance.com",
    ("futures", True): "https://testnet.binancefuture.com",
    ("futures", False): "https://fapi.binance.com",
}


def _setting(settings: object, section: str, name: str) -> object:
    try:
        return getattr(getattr(settings, section), name)
    except AttributeError as exc:
        raise ConfigError(f"Settings are missing {section}.{name}.") from exc


def _default_http(method: str, url: str, headers: dict[str, str], timeout: float) -> tuple[int, str]:
    request = Request(url, headers=headers, method=method)
    try:
        with urlopen(request, timeout=timeout) as response:
            return int(response.status), response.read().decode("utf-8")
    except HTTPError as exc:
        return int(exc.code), exc.read().decode("utf-8", errors="replace")
    except (URLError, TimeoutError, OSError) as exc:
        raise ExchangeError("Binance HTTP request failed.") from exc


class BinanceClient:
    """Read-only Binance client; it intentionally has no order-placement method."""

    def __init__(self, settings: object, http: HttpCallable | None = None) -> None:
        self.settings = settings
        market_type = str(_setting(settings, "exchange", "market_type"))
        testnet = bool(_setting(settings, "exchange", "testnet"))
        try:
            self.base_url = _BASE_URLS[(market_type, testnet)]
        except KeyError as exc:
            raise ConfigError("Exchange market_type must be spot or futures.") from exc
        self._http = http or _default_http
        self.timeout = float(_setting(settings, "exchange", "request_timeout_seconds"))

    @staticmethod
    def _signature(query_string: str, secret: str) -> str:
        return hmac.new(secret.encode(), query_string.encode(), hashlib.sha256).hexdigest()

    def _request(self, path: str, params: Mapping[str, object] | None = None,
                 headers: dict[str, str] | None = None) -> object:
        query = urlencode(list((params or {}).items()), doseq=True)
        url = self.base_url.rstrip("/") + "/" + path.lstrip("/")
        if query:
            url += "?" + query
        try:
            status, body = self._http("GET", url, headers or {}, self.timeout)
        except ExchangeError:
            raise
        except Exception as exc:
            raise ExchangeError("Binance HTTP request failed.") from exc
        if status < 200 or status >= 300:
            raise ExchangeError(f"Binance request failed with HTTP {status}.")
        try:
            return json.loads(body)
        except (TypeError, json.JSONDecodeError) as exc:
            raise ExchangeError(f"Binance returned invalid JSON (HTTP {status}).") from exc

    def public_get(self, path: str, params: Mapping[str, object] | None = None) -> object:
        return self._request(path, params)

    def signed_get(self, path: str, params: Mapping[str, object] | None = None) -> object:
        testnet = bool(_setting(self.settings, "exchange", "testnet"))
        mode = str(_setting(self.settings, "agent", "mode"))
        if not testnet and mode != "live":
            raise LiveTradingNotAllowed("Signed mainnet requests require live mode.")
        api_key = os.environ.get("BINANCE_API_KEY", "")
        secret = os.environ.get("BINANCE_API_SECRET", "")
        if not api_key or not secret:
            raise ConfigError("Signed requests require BINANCE_API_KEY and BINANCE_API_SECRET environment variables.")
        query_params = dict(params or {})
        query_params["timestamp"] = int(time.time() * 1000)
        query_params["recvWindow"] = int(_setting(self.settings, "exchange", "recv_window_ms"))
        query_string = urlencode(list(query_params.items()), doseq=True)
        signed_params = dict(query_params)
        signed_params["signature"] = self._signature(query_string, secret)
        return self._request(path, signed_params, {"X-MBX-APIKEY": api_key})
