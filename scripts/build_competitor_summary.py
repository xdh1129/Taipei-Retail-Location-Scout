from __future__ import annotations

import sys
from pathlib import Path
import csv
import io
import json
from datetime import date
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from retail_scout.data_catalog import RESTAURANT_COMPETITION_SOURCES
from retail_scout.features import DEMO_STATIONS, count_active_restaurants_by_district


RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"
COUNTS_PATH = PROCESSED_DIR / "competitor_counts_by_district.csv"
MANIFEST_PATH = PROCESSED_DIR / "competitor_summary_manifest.json"


def stream_csv_rows(url: str) -> list[dict[str, str]]:
    request = Request(url, headers={"User-Agent": "TaipeiRetailLocationScout/0.1"})
    with urlopen(request, timeout=90) as response:
        text_stream = io.TextIOWrapper(response, encoding="utf-8-sig", newline="")
        return list(csv.DictReader(text_stream))


def write_competitor_counts(path: Path, counts: dict[str, int]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["district", "active_restaurant_count"])
        writer.writeheader()
        for district in sorted(counts):
            writer.writerow(
                {
                    "district": district,
                    "active_restaurant_count": counts[district],
                }
            )


def main() -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    manifest = {
        "access_date": date.today().isoformat(),
        "collection_mode": "streamed_source_csv_to_district_summary",
        "sources": [],
    }
    districts = sorted({station.district for station in DEMO_STATIONS})

    for source in RESTAURANT_COMPETITION_SOURCES:
        print(f"Streaming {source.source_id} -> {COUNTS_PATH}")
        rows = stream_csv_rows(source.download_url)
        counts = count_active_restaurants_by_district(rows, districts=districts)
        write_competitor_counts(COUNTS_PATH, counts)
        manifest["sources"].append(
            {
                "source_id": source.source_id,
                "title": source.title,
                "dataset_page": source.dataset_page,
                "download_url": source.download_url,
                "derived_path": str(COUNTS_PATH.relative_to(ROOT)),
                "agency": source.agency,
                "license": source.license,
            }
        )

    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
