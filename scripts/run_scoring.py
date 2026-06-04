from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from retail_scout.scoring import compute_location_scores


PROCESSED_INPUT_PATH = ROOT / "data" / "processed" / "station_features.csv"
SAMPLE_INPUT_PATH = ROOT / "data" / "sample" / "station_features.csv"
OUTPUT_PATH = ROOT / "data" / "processed" / "station_scores.csv"
NUMERIC_COLUMNS = {
    "monthly_entries_exits",
    "target_population",
    "competitor_count",
    "real_estate_cost_index",
    "transport_access_index",
}


def choose_feature_input_path(
    *,
    processed_path: Path,
    sample_path: Path,
    processed_exists: bool | None = None,
) -> Path:
    if processed_exists is None:
        processed_exists = processed_path.exists()
    return processed_path if processed_exists else sample_path


def load_feature_rows(path: Path) -> list[dict[str, object]]:
    with path.open(newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        rows: list[dict[str, object]] = []
        for row in reader:
            converted: dict[str, object] = {}
            for key, value in row.items():
                converted[key] = float(value) if key in NUMERIC_COLUMNS else value
            rows.append(converted)
        return rows


def write_scores(path: Path, rows: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = [
        "station_name",
        "monthly_entries_exits",
        "target_population",
        "competitor_count",
        "real_estate_cost_index",
        "transport_access_index",
        "location_score",
        "recommendation_reason",
    ]
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    input_path = choose_feature_input_path(
        processed_path=PROCESSED_INPUT_PATH,
        sample_path=SAMPLE_INPUT_PATH,
    )
    rows = load_feature_rows(input_path)
    scored_rows = compute_location_scores(rows)
    write_scores(OUTPUT_PATH, scored_rows)
    print(f"Read feature rows from {input_path}")
    print(f"Wrote {len(scored_rows)} scored station rows to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
