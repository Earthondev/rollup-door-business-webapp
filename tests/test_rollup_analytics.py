import unittest
from datetime import date

from rollup_door.sheets import summarize_cases


class RollupAnalyticsTests(unittest.TestCase):
    def test_summary_filters_dates_and_counts_risk(self):
        rows = [
            {
                "created_at": "2026-03-01T10:00:00",
                "gross_margin_pct": "25",
                "material_cost": "2000",
                "labor_cost": "1000",
                "travel_cost": "200",
                "risk_buffer_cost": "100",
                "warranty_buffer_cost": "50",
            },
            {
                "created_at": "2026-03-02T10:00:00",
                "gross_margin_pct": "10",
                "material_cost": "3000",
                "labor_cost": "1500",
                "travel_cost": "300",
                "risk_buffer_cost": "150",
                "warranty_buffer_cost": "80",
            },
        ]

        out = summarize_cases(
            rows=rows,
            from_date=date(2026, 3, 2),
            to_date=date(2026, 3, 2),
            margin_threshold_pct=20,
        )

        self.assertEqual(out["total_cases"], 1)
        self.assertEqual(out["loss_risk_cases"], 1)
        self.assertEqual(out["avg_margin_pct"], 10.0)
        self.assertTrue(out["top_cost_drivers"])


if __name__ == "__main__":
    unittest.main()
