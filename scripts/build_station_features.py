from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from retail_scout.pipeline import connect, export_table, run_full_pipeline

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
# Land value has no live download yet; a tracked, documented stand-in is read
# directly from data/reference/ (see data/reference/README.md).
LAND_VALUE_PATH = ROOT / "data" / "reference" / "land_value_by_district.csv"


def main() -> None:
    con = connect()
    dropped = run_full_pipeline(
        con,
        mrt_csv=RAW_DIR / "mrt_station_entries.csv",
        entrances_csv=RAW_DIR / "mrt_entrances.csv",
        population_csv=RAW_DIR / "population_by_village.csv",
        registry_csv=RAW_DIR / "restaurant_businesses.csv",
        districts_geo=RAW_DIR / "taipei_districts.json",
        land_value_csv=LAND_VALUE_PATH,
    )
    export_table(
        con, "mart_station_features",
        PROCESSED_DIR / "station_features.parquet",
        PROCESSED_DIR / "station_features.csv",
    )
    kept = con.execute("SELECT count(*) FROM mart_station_features").fetchone()[0]
    print(
        f"Wrote {kept} station feature rows; dropped {dropped} stations not resolvable "
        "to a complete Taipei City district profile."
    )


if __name__ == "__main__":
    main()
