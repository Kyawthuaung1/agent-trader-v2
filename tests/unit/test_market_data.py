from __future__ import annotations
import sys, unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from agent_trader.exchange.market_data import get_klines, get_last_price, get_server_time, get_symbol_filters
class FakeClient:
    def __init__(self, market, response):
        self.settings=SimpleNamespace(exchange=SimpleNamespace(market_type=market))
        self.response=response; self.calls=[]
    def public_get(self, path, params=None):
        self.calls.append((path,params)); return self.response
class MarketDataTests(unittest.TestCase):
    def test_klines_parse_from_fake(self):
        fake=FakeClient("spot", [[1000,"1","2","0.5","1.5","4",1999]])
        candles=get_klines(fake,"BTCUSDT","1m",10)
        self.assertEqual(candles[0].close,1.5); self.assertEqual(fake.calls[0][0],"/api/v3/klines")
        self.assertEqual(fake.calls[0][1],{"symbol":"BTCUSDT","interval":"1m","limit":10})
    def test_futures_time_and_price_paths(self):
        fake=FakeClient("futures", {"serverTime":123,"price":"12.5"})
        self.assertEqual(get_server_time(fake),123); self.assertEqual(get_last_price(fake,"BTCUSDT"),12.5)
        self.assertEqual(fake.calls[0][0],"/fapi/v1/time"); self.assertEqual(fake.calls[1][0],"/fapi/v1/ticker/price")
    def test_filters_return_decimal_strings(self):
        data={"symbols":[{"symbol":"BTCUSDT","filters":[
            {"filterType":"LOT_SIZE","stepSize":"0.001","minQty":"0.001"},
            {"filterType":"PRICE_FILTER","tickSize":"0.01"},
            {"filterType":"MIN_NOTIONAL","minNotional":"5"}]}]}
        self.assertEqual(get_symbol_filters(FakeClient("spot",data),"BTCUSDT"),
            {"tick_size":"0.01","step_size":"0.001","min_notional":"5","min_qty":"0.001"})
if __name__ == "__main__": unittest.main()
