from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from agent_trader.exchange.orders import OrderRequest, build_order_params, validate_order
from agent_trader.utils.errors import RiskViolation
FILTERS={"step_size":"0.01","tick_size":"0.1","min_qty":"0.01","min_notional":"10"}
class OrderTests(unittest.TestCase):
    def test_valid_and_build_params(self):
        req=OrderRequest("BTCUSDT","BUY","LIMIT","0.10","100.0")
        validate_order(req,FILTERS)
        self.assertEqual(build_order_params(req), {"symbol":"BTCUSDT","side":"BUY","type":"LIMIT",
            "quantity":"0.10","price":"100.0","timeInForce":"GTC"})
    def test_bad_quantity_rejected(self):
        for quantity in ("0.105","0.001"):
            with self.subTest(quantity=quantity), self.assertRaises(RiskViolation):
                validate_order(OrderRequest("BTCUSDT","BUY","LIMIT",quantity,"100"),FILTERS)
    def test_bad_price_tick_rejected(self):
        with self.assertRaises(RiskViolation):
            validate_order(OrderRequest("BTCUSDT","BUY","LIMIT","1","100.05"),FILTERS)
    def test_min_notional_rejected(self):
        with self.assertRaises(RiskViolation):
            validate_order(OrderRequest("BTCUSDT","BUY","LIMIT","0.05","100"),FILTERS)
    def test_order_module_only_builds_data(self):
        req=OrderRequest("BTCUSDT","SELL","STOP_LOSS_LIMIT","0.10","100","99",True)
        params=build_order_params(req)
        self.assertEqual(params["stopPrice"],"99"); self.assertEqual(params["reduceOnly"],"true")
        self.assertFalse(hasattr(req,"send"))
if __name__ == "__main__": unittest.main()
