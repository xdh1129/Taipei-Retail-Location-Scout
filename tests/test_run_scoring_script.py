import unittest
import tempfile
from pathlib import Path

from scripts.run_scoring import choose_feature_input_path, write_scores


class RunScoringScriptTests(unittest.TestCase):
    def test_choose_feature_input_path_prefers_processed_features(self):
        result = choose_feature_input_path(
            processed_path=Path("data/processed/station_features.csv"),
            sample_path=Path("data/sample/station_features.csv"),
            processed_exists=True,
        )

        self.assertEqual(result, Path("data/processed/station_features.csv"))

    def test_choose_feature_input_path_falls_back_to_sample(self):
        result = choose_feature_input_path(
            processed_path=Path("data/processed/station_features.csv"),
            sample_path=Path("data/sample/station_features.csv"),
            processed_exists=False,
        )

        self.assertEqual(result, Path("data/sample/station_features.csv"))

    def test_write_scores_includes_economic_opportunity_fields(self):
        row = {
            "station_name": "A",
            "monthly_entries_exits": 1000.0,
            "target_population": 500.0,
            "competitor_count": 50.0,
            "real_estate_cost_index": 80.0,
            "transport_access_index": 0.5,
            "accessible_demand": 100.0,
            "competition_adjusted_customers": 60.0,
            "estimated_monthly_revenue": 9600.0,
            "estimated_gross_profit": 5952.0,
            "operating_cost_proxy": 720000.0,
            "feasibility_ratio": 0.0083,
            "economic_opportunity_index": 0.83,
            "profit_gap_proxy": -714048.0,
            "break_even_capture_rate": 72.58,
            "location_score": 40.0,
            "recommendation_reason": "higher-risk economics under current assumptions",
        }
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "scores.csv"

            write_scores(output_path, [row])

            raw_content = output_path.read_bytes()
            content = raw_content.decode("utf-8")
            header = content.splitlines()[0]

        self.assertIn("accessible_demand", header)
        self.assertIn("feasibility_ratio", header)
        self.assertIn("economic_opportunity_index", header)
        self.assertIn("profit_gap_proxy", header)
        self.assertIn("break_even_capture_rate", header)
        self.assertNotIn(b"\r", raw_content)


if __name__ == "__main__":
    unittest.main()
