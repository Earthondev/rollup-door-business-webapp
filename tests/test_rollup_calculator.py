import unittest

from rollup_door.calculator import estimate_price, evaluate_margin


class RollupCalculatorTests(unittest.TestCase):
    def test_estimate_price_returns_expected_shape(self):
        out = estimate_price(
            material_cost=20000,
            labor_cost=5000,
            travel_cost=1000,
            risk_level="medium",
            warranty_months=12,
            target_margin_pct=30,
        )
        self.assertGreater(out.direct_cost, 0)
        self.assertGreater(out.suggested_price, out.direct_cost)
        self.assertAlmostEqual(out.gross_margin_pct, 30.0, places=1)

    def test_evaluate_margin(self):
        gp, gm = evaluate_margin(final_price=100000, direct_cost=70000)
        self.assertEqual(gp, 30000.0)
        self.assertEqual(gm, 30.0)


if __name__ == "__main__":
    unittest.main()
