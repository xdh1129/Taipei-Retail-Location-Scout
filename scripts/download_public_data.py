from __future__ import annotations

import json
import sys
from datetime import date
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from retail_scout.data_catalog import (
    CORE_PUBLIC_SOURCES,
    GEO_PUBLIC_SOURCES,
    RESTAURANT_COMPETITION_SOURCES,
    build_manifest,
    is_probable_csv_payload,
    is_probable_json_payload,
    is_probable_zip_payload,
)


RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "public_data_manifest.json"


def kind_for(raw_filename: str) -> str:
    if raw_filename.endswith(".zip"):
        return "zip"
    if raw_filename.endswith((".json", ".geojson")):
        return "json"
    return "csv"


def download_file(url: str, output_path: Path, *, kind: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "TaipeiRetailLocationScout/0.1"})
    with urlopen(request, timeout=120) as response:
        payload = response.read()
        if kind == "csv" and not is_probable_csv_payload(payload):
            raise ValueError(f"Downloaded payload does not look like CSV: {url}")
        if kind == "zip" and not is_probable_zip_payload(payload):
            raise ValueError(f"Downloaded payload does not look like a zip: {url}")
        if kind == "json" and not is_probable_json_payload(payload):
            raise ValueError(f"Downloaded payload does not look like JSON: {url}")
        output_path.write_bytes(payload)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for source in (
        CORE_PUBLIC_SOURCES + RESTAURANT_COMPETITION_SOURCES + GEO_PUBLIC_SOURCES
    ):
        target = source.raw_path(RAW_DIR)
        kind = kind_for(source.raw_filename)
        print(f"Downloading {source.source_id} -> {target}")
        download_file(source.download_url, target, kind=kind)

    manifest = build_manifest(RAW_DIR.relative_to(ROOT), access_date=date.today().isoformat())
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
