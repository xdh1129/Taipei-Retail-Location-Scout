import unittest

from retail_scout.scoring import compute_location_scores, normalize_values


class ScoringTests(unittest.TestCase):
    def test_normalize_values_maps_range_to_zero_one(self):
        values = [10, 20, 30]

        self.assertEqual(normalize_values(values), [0.0, 0.5, 1.0])

    def test_normalize_values_returns_zero_for_constant_series(self):
        values = [7, 7, 7]

        self.assertEqual(normalize_values(values), [0.0, 0.0, 0.0])

    def test_compute_location_scores_prioritizes_balanced_high_demand_area(self):
        rows = [
            {
                "station_name": "A",
                "monthly_entries_exits": 1000,
                "target_population": 500,
                "competitor_count": 20,
                "real_estate_cost_index": 90,
                "transport_access_index": 1.0,
            },
            {
                "station_name": "B",
                "monthly_entries_exits": 900,
                "target_population": 800,
                "competitor_count": 4,
                "real_estate_cost_index": 60,
                "transport_access_index": 0.8,
            },
        ]

        scored = compute_location_scores(rows)

        self.assertEqual(scored[0]["station_name"], "B")
        self.assertGreater(scored[0]["location_score"], scored[1]["location_score"])
        self.assertIn("strong demand-to-competition gap", scored[0]["recommendation_reason"])


if __name__ == "__main__":
    unittest.main()
