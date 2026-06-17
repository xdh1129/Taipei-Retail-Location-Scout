import unittest
from pathlib import Path

from retail_scout.data_catalog import (
    CORE_PUBLIC_SOURCES,
    RESTAURANT_COMPETITION_SOURCES,
    build_manifest,
    is_probable_csv_payload,
)


class DataCatalogTests(unittest.TestCase):
    def test_core_public_sources_include_required_raw_files(self):
        raw_filenames = {source.raw_filename for source in CORE_PUBLIC_SOURCES}

        self.assertEqual(
            raw_filenames,
            {
                "mrt_station_entries.csv",
                "mrt_entrances.csv",
                "population_by_village.csv",
            },
        )

    def test_restaurant_competition_sources_include_restaurant_businesses(self):
        raw_filenames = {
            source.raw_filename for source in RESTAURANT_COMPETITION_SOURCES
        }

        self.assertEqual(raw_filenames, {"restaurant_businesses.csv"})

    def test_build_manifest_records_access_date_and_paths(self):
        manifest = build_manifest(
            raw_dir=Path("data/raw"),
            access_date="2026-06-04",
        )

        self.assertEqual(manifest["access_date"], "2026-06-04")
        self.assertEqual(len(manifest["sources"]), 3)
        self.assertEqual(
            manifest["sources"][0]["raw_path"],
            "data/raw/mrt_station_entries.csv",
        )
        self.assertIn("license", manifest["sources"][0])

    def test_is_probable_csv_payload_rejects_html_error_page(self):
        self.assertFalse(is_probable_csv_payload(b"<!DOCTYPE html><html></html>"))
        self.assertTrue(is_probable_csv_payload("a,b,c\n1,2,3\n".encode("utf-8")))

    def test_geo_public_sources_provide_downloadable_boundary(self):
        from retail_scout.data_catalog import GEO_PUBLIC_SOURCES

        source_ids = {source.source_id for source in GEO_PUBLIC_SOURCES}
        self.assertEqual(source_ids, {"taipei_districts"})
        districts = GEO_PUBLIC_SOURCES[0]
        self.assertEqual(districts.raw_filename, "taipei_districts.json")
        self.assertTrue(districts.dataset_page.startswith("http"))
        self.assertTrue(districts.download_url.startswith("http"))

    def test_land_value_standin_is_bundled_in_repo(self):
        from retail_scout.data_catalog import LAND_VALUE_STANDIN_PATH

        path = Path(__file__).resolve().parents[1] / LAND_VALUE_STANDIN_PATH
        self.assertTrue(path.exists(), f"missing bundled land-value stand-in: {path}")
        header = path.read_text(encoding="utf-8").splitlines()[0]
        self.assertEqual(header, "district,land_value")

    def test_is_probable_zip_payload_detects_zip_magic(self):
        from retail_scout.data_catalog import is_probable_zip_payload

        self.assertTrue(is_probable_zip_payload(b"PK\x03\x04rest-of-zip"))
        self.assertFalse(is_probable_zip_payload(b"<!DOCTYPE html>"))

    def test_is_probable_json_payload_detects_json(self):
        from retail_scout.data_catalog import is_probable_json_payload

        self.assertTrue(is_probable_json_payload(b'  {"type":"Topology"}'))
        self.assertTrue(is_probable_json_payload(b"[1, 2, 3]"))
        self.assertFalse(is_probable_json_payload(b"<!DOCTYPE html>"))


if __name__ == "__main__":
    unittest.main()
