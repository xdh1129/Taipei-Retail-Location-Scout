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
    build_manifest,
    is_probable_csv_payload,
)


RAW_DIR = ROOT / "data" / "raw"
MANIFEST_PATH = RAW_DIR / "public_data_manifest.json"


def download_file(url: str, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "TaipeiRetailLocationScout/0.1"})
    with urlopen(request, timeout=60) as response:
        payload = response.read()
        if not is_probable_csv_payload(payload):
            raise ValueError(f"Downloaded payload does not look like CSV: {url}")
        output_path.write_bytes(payload)


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    for source in CORE_PUBLIC_SOURCES:
        target = source.raw_path(RAW_DIR)
        print(f"Downloading {source.source_id} -> {target}")
        download_file(source.download_url, target)

    manifest = build_manifest(RAW_DIR.relative_to(ROOT), access_date=date.today().isoformat())
    MANIFEST_PATH.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote manifest -> {MANIFEST_PATH}")


if __name__ == "__main__":
    main()
