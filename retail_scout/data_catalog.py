from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


OPEN_GOV_LICENSE = "Open Government Data License, version 1.0"


@dataclass(frozen=True)
class RawDataSource:
    source_id: str
    title: str
    dataset_page: str
    download_url: str
    raw_filename: str
    agency: str
    license: str = OPEN_GOV_LICENSE

    def raw_path(self, raw_dir: Path) -> Path:
        return raw_dir / self.raw_filename


CORE_PUBLIC_SOURCES = [
    RawDataSource(
        source_id="mrt_station_entries",
        title="Taipei MRT station entries and exits time series",
        dataset_page="https://data.gov.tw/dataset/133184",
        download_url=(
            "https://tsis.dbas.gov.taipei/statis/webMain.aspx?"
            "sys=220&funid=a05023601&cycle=4&outmode=12&compmode=0"
            "&outkind=3&deflst=2&nzo=1&type=0&ymf=8500&ymt=11400&kind=21"
        ),
        raw_filename="mrt_station_entries.csv",
        agency="Taipei City Government Department of Budget, Accounting and Statistics",
    ),
    RawDataSource(
        source_id="mrt_entrances",
        title="Coordinates of Taipei MRT station entrances and exits",
        dataset_page="https://data.gov.tw/en/datasets/128428",
        download_url=(
            "https://scidm.nchc.org.tw/en/dataset/best_wish128428/"
            "resource/60296981-c2e4-4766-a1e8-4ec8b4448af6/nchcproxy"
        ),
        raw_filename="mrt_entrances.csv",
        agency="Taipei Rapid Transit Corporation",
    ),
    RawDataSource(
        source_id="population_by_village",
        title="Village household and single-age population, 2026-04",
        dataset_page="https://data.gov.tw/dataset/77132",
        download_url=(
            "https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/"
            "2C7688CB-B505-4D00-B11C-66C4D31B024F/resource/"
            "44EDEF1F-EBDC-4CF0-9C6D-E845875CECF1/download"
        ),
        raw_filename="population_by_village.csv",
        agency="Department of Household Registration, Ministry of the Interior",
    ),
]


RESTAURANT_COMPETITION_SOURCES = [
    RawDataSource(
        source_id="restaurant_businesses",
        title="Business registrations by business item: restaurants",
        dataset_page="https://data.gov.tw/dataset/108355",
        download_url=(
            "https://data.gcis.nat.gov.tw/od/file?"
            "oid=D6F37400-1426-4C06-B330-2E344F3F73AB"
        ),
        raw_filename="restaurant_businesses.csv",
        agency="Administration of Commerce, Ministry of Economic Affairs",
    ),
]


def build_manifest(raw_dir: Path, access_date: str) -> dict[str, object]:
    return {
        "access_date": access_date,
        "sources": [
            {
                "source_id": source.source_id,
                "title": source.title,
                "dataset_page": source.dataset_page,
                "download_url": source.download_url,
                "raw_path": str(source.raw_path(raw_dir)),
                "agency": source.agency,
                "license": source.license,
            }
            for source in CORE_PUBLIC_SOURCES
        ],
    }


def is_probable_csv_payload(payload: bytes) -> bool:
    stripped = payload.lstrip()
    lowered = stripped[:200].lower()
    if lowered.startswith(b"<!doctype html") or lowered.startswith(b"<html"):
        return False

    sample = stripped[:4096]
    return b"," in sample and (b"\n" in sample or b"\r" in sample)
