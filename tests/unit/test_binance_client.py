from __future__ import annotations
import json, os, re, sys, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from urllib.parse import parse_qs, urlencode, urlparse
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from agent_trader.exchange.binance_client import BinanceClient
from agent_trader.utils.errors import ConfigError, ExchangeError, LiveTradingNotAllowed
def settings(market="spot", testnet=True, mode="paper"):
    return SimpleNamespace(agent=SimpleNamespace(mode=mode), exchange=SimpleNamespace(
        market_type=market, testnet=testnet, request_timeout_seconds=3, recv_window_ms=5000))
class BinanceClientTests(unittest.TestCase):
    def test_all_four_base_urls(self):
        expected = {("spot", True): "https://testnet.binance.vision",
                    ("spot", False): "https://api.binance.com",
                    ("futures", True): "https://testnet.binancefuture.com",
                    ("futures", False): "https://fapi.binance.com"}
        for combination, url in expected.items():
            with self.subTest(combination=combination):
                self.assertEqual(BinanceClient(settings(*combination)).base_url, url)
    def test_signature_is_hex_deterministic_and_param_sensitive(self):
        secret = "fake-secret"
        base = {"symbol": "BTCUSDT", "timestamp": 123, "recvWindow": 5000}
        signature = BinanceClient._signature(urlencode(base), secret)
        self.assertRegex(signature, re.compile(r"^[0-9a-f]{64}$"))
        self.assertEqual(signature, BinanceClient._signature(urlencode(base), secret))
        for key, value in (("symbol", "ETHUSDT"), ("timestamp", 124), ("recvWindow", 4000)):
            changed = dict(base); changed[key] = value
            self.assertNotEqual(signature, BinanceClient._signature(urlencode(changed), secret))
    def test_signed_mainnet_refused_unless_live(self):
        client = BinanceClient(settings("spot", False, "paper"), http=lambda *args: (200, "{}"))
        with self.assertRaises(LiveTradingNotAllowed): client.signed_get("/api/v3/account")
    def test_missing_keys_fail_without_request(self):
        client = BinanceClient(settings(), http=lambda *args: (200, "{}"))
        with patch.dict(os.environ, {}, clear=True):
            with self.assertRaisesRegex(ConfigError, "BINANCE_API_KEY"): client.signed_get("/api/v3/account")
    def test_status_error_does_not_leak_secret_body(self):
        secret = "fake-only-secret"
        client = BinanceClient(settings(), http=lambda *args: (500, json.dumps({"error": secret})))
        with patch.dict(os.environ, {"BINANCE_API_KEY":"fake-key", "BINANCE_API_SECRET":secret}):
            with self.assertRaises(ExchangeError) as caught: client.signed_get("/api/v3/account")
        self.assertNotIn(secret, str(caught.exception)); self.assertIn("500", str(caught.exception))
    def test_signed_request_uses_fake_http(self):
        seen = []
        def fake(method, url, headers, timeout):
            seen.append((method,url,headers,timeout)); return 200, "{}"
        client = BinanceClient(settings(), http=fake)
        with patch.dict(os.environ, {"BINANCE_API_KEY":"fake-key", "BINANCE_API_SECRET":"fake-secret"}):
            client.signed_get("/api/v3/account", {"symbol":"BTCUSDT"})
        method,url,headers,timeout = seen[0]; query=parse_qs(urlparse(url).query)
        self.assertEqual(method, "GET"); self.assertEqual(headers["X-MBX-APIKEY"], "fake-key")
        self.assertEqual(len(query["signature"][0]), 64); self.assertEqual(query["recvWindow"], ["5000"])
        self.assertEqual(query["symbol"], ["BTCUSDT"]); self.assertEqual(timeout, 3.0)
    def test_invalid_json_error_is_safe(self):
        client = BinanceClient(settings(), http=lambda *args: (200, "not-json-secret"))
        with self.assertRaises(ExchangeError) as caught: client.public_get("/api/v3/time")
        self.assertNotIn("not-json-secret", str(caught.exception))
if __name__ == "__main__": unittest.main()
