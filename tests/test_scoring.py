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

    def test_compute_location_scores_outputs_economic_opportunity_metrics(self):
        rows = [
            {
                "station_name": "A",
                "monthly_entries_exits": 1_000_000,
                "target_population": 30_000,
                "competitor_count": 300,
                "real_estate_cost_index": 80,
                "transport_access_index": 0.7,
            },
            {
                "station_name": "B",
                "monthly_entries_exits": 600_000,
                "target_population": 60_000,
                "competitor_count": 80,
                "real_estate_cost_index": 55,
                "transport_access_index": 0.6,
            },
        ]

        scored = compute_location_scores(rows)
        top = scored[0]

        for field in [
            "accessible_demand",
            "competition_adjusted_customers",
            "estimated_monthly_revenue",
            "estimated_gross_profit",
            "operating_cost_proxy",
            "feasibility_ratio",
            "economic_opportunity_index",
            "profit_gap_proxy",
            "break_even_capture_rate",
        ]:
            self.assertIn(field, top)

        self.assertGreater(top["accessible_demand"], 0)
        self.assertGreater(top["competition_adjusted_customers"], 0)
        self.assertGreater(top["estimated_monthly_revenue"], 0)
        self.assertGreater(top["estimated_gross_profit"], 0)
        self.assertGreater(top["operating_cost_proxy"], 0)
        self.assertGreater(top["feasibility_ratio"], 0)
        self.assertGreaterEqual(top["economic_opportunity_index"], 0)
        self.assertLessEqual(top["economic_opportunity_index"], 100)
        self.assertEqual(top["location_score"], top["economic_opportunity_index"])
        self.assertGreater(top["break_even_capture_rate"], 0)

    def test_feasibility_model_penalizes_cost_and_competition_pressure(self):
        rows = [
            {
                "station_name": "High Footfall Expensive Area",
                "monthly_entries_exits": 1_200_000,
                "target_population": 20_000,
                "competitor_count": 600,
                "real_estate_cost_index": 100,
                "transport_access_index": 1.0,
            },
            {
                "station_name": "Balanced Opportunity Area",
                "monthly_entries_exits": 700_000,
                "target_population": 65_000,
                "competitor_count": 80,
                "real_estate_cost_index": 55,
                "transport_access_index": 0.7,
            },
        ]

        scored = compute_location_scores(rows)

        self.assertEqual(scored[0]["station_name"], "Balanced Opportunity Area")
        self.assertGreater(scored[0]["feasibility_ratio"], scored[1]["feasibility_ratio"])
        self.assertEqual(scored[0]["location_score"], 100.0)
        self.assertIn(
            "clears cost proxy under current assumptions",
            scored[0]["recommendation_reason"],
        )


if __name__ == "__main__":
    unittest.main()
