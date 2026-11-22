from __future__ import annotations
import sys, unittest
from pathlib import Path
from tempfile import TemporaryDirectory
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from agent_trader.data.candles import Candle, drop_unclosed, parse_klines
from agent_trader.data.storage import load_candles, save_candles
class CandleTests(unittest.TestCase):
    def test_parse_and_drop_unclosed(self):
        rows = [[1000, "1", "3", "0.5", "2", "10", 1999]]
        candles = parse_klines(rows)
        self.assertEqual(candles, [Candle(1000, 1.0, 3.0, 0.5, 2.0, 10.0, 1999)])
        self.assertEqual(drop_unclosed(candles, 1999), [])
        self.assertEqual(drop_unclosed(candles, 2000), candles)
    def test_csv_round_trip_creates_parent(self):
        candle = Candle(1, 1.0, 2.0, 0.5, 1.5, 5.0, 2)
        with TemporaryDirectory() as folder:
            path = Path(folder) / "new" / "candles.csv"
            save_candles(path, [candle])
            self.assertEqual(load_candles(path), [candle])
    def test_short_kline_fails(self):
        with self.assertRaises(ValueError): parse_klines([[1, 2]])
if __name__ == "__main__": unittest.main()
