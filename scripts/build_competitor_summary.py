from __future__ import annotations

import sys
from datetime import date
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from retail_scout.data_catalog import RESTAURANT_COMPETITION_SOURCES
from retail_scout.pipeline import connect, stage_competitors

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
REGISTRY_PATH = RAW_DIR / "restaurant_businesses.csv"
COUNTS_PATH = PROCESSED_DIR / "competitor_counts_by_district.csv"
MANIFEST_PATH = PROCESSED_DIR / "competitor_summary_manifest.json"


def main() -> None:
    if not REGISTRY_PATH.exists():
        raise SystemExit("Missing restaurant_businesses.csv. Run scripts/download_public_data.py first.")
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    con = connect()
    con.execute(f"CREATE TABLE raw_registry AS SELECT * FROM read_csv_auto('{REGISTRY_PATH}', header=true)")
    stage_competitors(con)
    con.execute(
        f"COPY (SELECT district, competitor_count AS active_restaurant_count "
        f"FROM stg_competitors ORDER BY district) TO '{COUNTS_PATH}' (FORMAT CSV, HEADER)"
    )
    manifest = {
        "access_date": date.today().isoformat(),
        "collection_mode": "duckdb_full_registry_to_district_summary",
        "sources": [
            {
                "source_id": s.source_id, "title": s.title, "dataset_page": s.dataset_page,
                "download_url": s.download_url, "derived_path": str(COUNTS_PATH.relative_to(ROOT)),
                "agency": s.agency, "license": s.license,
            } for s in RESTAURANT_COMPETITION_SOURCES
        ],
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Wrote competitor counts -> {COUNTS_PATH}")


if __name__ == "__main__":
    main()
