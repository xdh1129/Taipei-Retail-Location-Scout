import unittest
from pathlib import Path

from scripts.run_scoring import choose_feature_input_path


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


if __name__ == "__main__":
    unittest.main()
