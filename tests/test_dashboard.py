import unittest

import pandas as pd

from retail_scout.dashboard import build_summary, filter_ranked_locations


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
                    "location_score": 70.0,
                    "recommendation_reason": "strong gap",
                },
            ]
        )

    def test_build_summary_reports_top_station_and_averages(self):
        summary = build_summary(self.df)

        self.assertEqual(summary["top_station"], "B")
        self.assertEqual(summary["top_score"], 70.0)
        self.assertEqual(summary["average_monthly_entries_exits"], 1500.0)
        self.assertEqual(summary["lowest_competition_station"], "B")

    def test_filter_ranked_locations_keeps_minimum_score_and_sort_order(self):
        result = filter_ranked_locations(self.df, minimum_score=50.0)

        self.assertEqual(result["station_name"].tolist(), ["B"])


if __name__ == "__main__":
    unittest.main()
