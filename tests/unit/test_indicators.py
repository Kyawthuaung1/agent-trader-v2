from __future__ import annotations
import sys, unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from agent_trader.data.indicators import atr, ema, rsi, sma
from agent_trader.utils.errors import ConfigError
class IndicatorTests(unittest.TestCase):
    def test_sma_ema_and_warmup(self):
        values = [1.0, 2.0, 3.0, 4.0]
        self.assertEqual(sma(values, 2), [None, 1.5, 2.5, 3.5])
        self.assertEqual(ema(values, 2), [None, 1.5, 2.5, 3.5])
    def test_rsi_wilder(self):
        self.assertEqual(rsi([1.0, 2.0, 1.0, 2.0], 2), [None, None, 50.0, 75.0])
        self.assertEqual(rsi([1.0, 2.0, 3.0], 2), [None, None, 100.0])
    def test_atr_wilder(self):
        result = atr([10, 12, 13], [8, 9, 11], [9, 11, 12], 2)
        self.assertEqual(result[0], None)
        self.assertAlmostEqual(result[1], 2.5)
        self.assertAlmostEqual(result[2], 2.25)
    def test_period_must_be_positive(self):
        for call in (lambda: sma([1], 0), lambda: ema([1], 0),
                     lambda: rsi([1], 0), lambda: atr([1], [0], [0.5], 0)):
            with self.assertRaises(ConfigError): call()
if __name__ == "__main__": unittest.main()
