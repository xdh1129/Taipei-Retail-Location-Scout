from __future__ import annotations

import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from retail_scout.features import (
    DEMO_STATIONS,
    build_station_feature_rows,
    extract_target_population_by_district,
)


RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
COMPETITOR_COUNTS_PATH = PROCESSED_DIR / "competitor_counts_by_district.csv"
OUTPUT_PATH = PROCESSED_DIR / "station_features.csv"
METADATA_PATH = PROCESSED_DIR / "station_features_metadata.json"


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def read_competitor_counts(path: Path) -> dict[str, int]:
    rows = read_csv(path)
    return {row["district"]: int(row["active_restaurant_count"]) for row in rows}


def write_dict_rows(path: Path, rows: list[dict[str, object]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    if not COMPETITOR_COUNTS_PATH.exists():
        raise SystemExit(
            "Missing competitor counts. Run `python3 scripts/build_competitor_summary.py` first."
        )

    mrt_rows = read_csv(RAW_DIR / "mrt_station_entries.csv")
    entrance_rows = read_csv(RAW_DIR / "mrt_entrances.csv")
    population_rows = read_csv(RAW_DIR / "population_by_village.csv")
    competitor_counts = read_competitor_counts(COMPETITOR_COUNTS_PATH)
    population_by_district = extract_target_population_by_district(population_rows)

    feature_rows = build_station_feature_rows(
        stations=DEMO_STATIONS,
        mrt_rows=mrt_rows,
        entrance_rows=entrance_rows,
        population_by_district=population_by_district,
        competitor_counts=competitor_counts,
    )

    write_dict_rows(
        OUTPUT_PATH,
        feature_rows,
        fieldnames=[
            "station_name",
            "monthly_entries_exits",
            "target_population",
            "competitor_count",
            "real_estate_cost_index",
            "transport_access_index",
        ],
    )
    METADATA_PATH.write_text(
        json.dumps(
            {
                "scope": "Six Taipei MRT-adjacent demo trade areas",
                "latest_mrt_period_rule": "Use the largest numeric ROC year in data/raw/mrt_station_entries.csv",
                "target_population_definition": "Residents aged 20-44 in the configured station district",
                "competitor_count_definition": "Active restaurant business registrations in the configured station district",
                "real_estate_cost_index_definition": "District-level proxy index documented in StationConfig",
                "transport_access_index_definition": "Station entrance count normalized within demo stations",
                "output": str(OUTPUT_PATH.relative_to(ROOT)),
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(feature_rows)} station feature rows -> {OUTPUT_PATH}")
    print(f"Wrote metadata -> {METADATA_PATH}")


if __name__ == "__main__":
    main()
