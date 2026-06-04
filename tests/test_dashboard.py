import unittest

import pandas as pd

from retail_scout.dashboard import build_summary, display_table, filter_ranked_locations


class DashboardTests(unittest.TestCase):
    def setUp(self):
        self.df = pd.DataFrame(
            [
                {
                    "station_name": "A",
                    "monthly_entries_exits": 1000.0,
                    "target_population": 500.0,
                    "competitor_count": 50.0,
                    "real_estate_cost_index": 80.0,
                    "transport_access_index": 0.5,
                    "accessible_demand": 800.0,
                    "competition_adjusted_customers": 300.0,
                    "estimated_monthly_revenue": 48000.0,
                    "estimated_gross_profit": 29760.0,
                    "operating_cost_proxy": 720000.0,
                    "feasibility_ratio": 0.0413,
                    "economic_opportunity_index": 4.13,
                    "profit_gap_proxy": -690240.0,
                    "break_even_capture_rate": 9.07,
                    "location_score": 40.0,
                    "recommendation_reason": "balanced",
                },
                {
                    "station_name": "B",
                    "monthly_entries_exits": 2000.0,
                    "target_population": 800.0,
                    "competitor_count": 20.0,
                    "real_estate_cost_index": 60.0,
                    "transport_access_index": 1.0,
                    "accessible_demand": 1200.0,
                    "competition_adjusted_customers": 700.0,
                    "estimated_monthly_revenue": 112000.0,
                    "estimated_gross_profit": 69440.0,
                    "operating_cost_proxy": 630000.0,
                    "feasibility_ratio": 0.1102,
                    "economic_opportunity_index": 11.02,
                    "profit_gap_proxy": -560560.0,
                    "break_even_capture_rate": 5.29,
                    "location_score": 70.0,
                    "recommendation_reason": "strong gap",
                },
            ]
        )

    def test_build_summary_reports_top_station_and_averages(self):
        summary = build_summary(self.df)

        self.assertEqual(summary["top_station"], "B")
        self.assertEqual(summary["top_score"], 70.0)
        self.assertEqual(summary["top_feasibility_ratio"], 0.1102)
        self.assertEqual(summary["average_monthly_entries_exits"], 1500.0)
        self.assertEqual(summary["lowest_competition_station"], "B")

    def test_filter_ranked_locations_keeps_minimum_score_and_sort_order(self):
        result = filter_ranked_locations(self.df, minimum_score=50.0)

        self.assertEqual(result["station_name"].tolist(), ["B"])

    def test_display_table_includes_economic_opportunity_columns(self):
        result = display_table(self.df)

        self.assertIn("economic_opportunity_index", result.columns)
        self.assertIn("feasibility_ratio", result.columns)
        self.assertIn("break_even_capture_rate", result.columns)
        self.assertIn("estimated_monthly_revenue", result.columns)
        self.assertNotIn("profit_gap_proxy", result.columns)


if __name__ == "__main__":
    unittest.main()
