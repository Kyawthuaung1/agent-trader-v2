import unittest
from decimal import Decimal

from agent_trader.risk.position_sizing import calc_position_size
from agent_trader.utils.errors import RiskViolation


class TestPositionSizing(unittest.TestCase):
    def setUp(self) -> None:
        self.filters = {
            "step_size": "0.01", "min_qty": "0.01", "min_notional": "5"
        }

    def test_hand_calculation_and_rounding_down(self) -> None:
        quantity = calc_position_size(
            equity=Decimal("1000"), risk_pct=Decimal("1"),
            entry=Decimal("101"), stop=Decimal("90"), filters=self.filters,
            max_leverage=Decimal("3"), market_type="futures"
        )
        self.assertEqual(quantity, Decimal("0.90"))
        self.assertIsInstance(quantity, Decimal)

    def test_leverage_cap_and_spot_forces_one_x(self) -> None:
        futures_quantity = calc_position_size(
            equity="1000", risk_pct="100", entry="100", stop="99",
            filters=self.filters, max_leverage="2", market_type="futures"
        )
        spot_quantity = calc_position_size(
            equity="1000", risk_pct="100", entry="100", stop="99",
            filters=self.filters, max_leverage="20", market_type="spot"
        )
        self.assertEqual(futures_quantity, Decimal("20.00"))
        self.assertEqual(spot_quantity, Decimal("10.00"))

    def test_refuses_invalid_values_and_exchange_minimums(self) -> None:
        invalid_cases = [
            {"equity": "0"}, {"risk_pct": "0"}, {"entry": "0"},
            {"stop": "0"}, {"max_leverage": "0"},
            {"entry": "100", "stop": "100"},
        ]
        base = {
            "equity": "1000", "risk_pct": "1", "entry": "100",
            "stop": "90", "filters": self.filters, "max_leverage": "2",
            "market_type": "futures",
        }
        for override in invalid_cases:
            with self.subTest(override=override), self.assertRaises(RiskViolation):
                calc_position_size(**(base | override))

        with self.assertRaises(RiskViolation):
            calc_position_size(
                equity="1", risk_pct="0.01", entry="100", stop="99",
                filters=self.filters, max_leverage="1", market_type="spot"
            )
        with self.assertRaises(RiskViolation):
            calc_position_size(
                equity="1000", risk_pct="1", entry="100", stop="99",
                filters={"step_size": "0.01", "min_qty": "0.01", "min_notional": "2000"},
                max_leverage="1", market_type="spot"
            )
        with self.assertRaises(RiskViolation):
            calc_position_size(
                equity="1000", risk_pct="1", entry="100", stop="99",
                filters=self.filters, max_leverage="2", market_type="margin"
            )


if __name__ == "__main__":
    unittest.main()
