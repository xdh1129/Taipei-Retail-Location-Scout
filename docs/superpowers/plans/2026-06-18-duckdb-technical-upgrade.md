# DuckDB Medallion Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the hardcoded six-station, pure-`csv` feature pipeline with a DuckDB-driven medallion pipeline that processes the full public datasets and scores all Taipei City MRT stations.

**Architecture:** Raw CSV/shapefile → DuckDB SQL staging transforms → Parquet staging tables → DuckDB join into a feature mart (Parquet + CSV) → existing scoring model → `station_scores.{parquet,csv}`. DuckDB is the only processing engine; spatial point-in-district join uses the DuckDB `spatial` extension. Transform logic lives in `retail_scout/pipeline.py` and is tested against small synthetic DuckDB tables.

**Tech Stack:** Python 3.12, DuckDB 1.5+ (with `spatial` extension), Parquet, `unittest`. (`geopandas`/`shapely` already in requirements as a fallback; not used if the DuckDB `spatial` path works.)

## Global Constraints

- Python standard `unittest` only; run via `python3 -m unittest ...`. No pytest.
- Tests use small synthetic in-memory DuckDB tables/fixtures — never the real multi-MB files. Suite must stay fast (<2s).
- Geographic scope is **Taipei City only**. Stations whose entrances fall outside Taipei City district polygons are dropped, and the dropped count is logged.
- Canonical district key is the normalized full form `臺北市{X}區` (e.g. `臺北市大安區`); all sources map to it. Normalize `台`→`臺` before keying.
- All processed outputs are written as **both** `.parquet` and `.csv`. The dashboard continues to read `data/processed/station_scores.csv` unchanged.
- The five mart feature columns, in order: `station_name`, `monthly_entries_exits`, `target_population`, `competitor_count`, `real_estate_cost_index`, `transport_access_index`.
- `real_estate_cost_index` must be min-max scaled into the range **[50, 100]** so the existing scoring calibration (`cost_index * 4500 + 360000`) stays meaningful.
- The scoring model in `retail_scout/scoring.py` is NOT changed.
- New dependency floor: add `duckdb>=1.0.0` is already present; ensure the `spatial` extension is installed/loaded at runtime via `INSTALL spatial; LOAD spatial;`.
- Commit after every task.

---

### Task 1: Register the two new raw data sources + download support

**Files:**
- Modify: `retail_scout/data_catalog.py`
- Modify: `scripts/download_public_data.py`
- Test: `tests/test_data_catalog.py`

**Interfaces:**
- Produces: `GEO_PUBLIC_SOURCES: list[RawDataSource]` containing `taipei_districts` (district boundary GeoJSON/zip) and `land_value_by_district` (公告地價/現值 CSV).
- Produces: `is_probable_zip_payload(payload: bytes) -> bool` in `data_catalog.py`.
- Produces: download script that fetches `CORE_PUBLIC_SOURCES + GEO_PUBLIC_SOURCES`, validating CSV sources with `is_probable_csv_payload` and the boundary source with `is_probable_zip_payload` OR a GeoJSON sniff.

- [ ] **Step 1: Write the failing test**

In `tests/test_data_catalog.py`, add:

```python
    def test_geo_public_sources_include_boundary_and_land_value(self):
        from retail_scout.data_catalog import GEO_PUBLIC_SOURCES

        source_ids = {source.source_id for source in GEO_PUBLIC_SOURCES}
        self.assertEqual(source_ids, {"taipei_districts", "land_value_by_district"})
        for source in GEO_PUBLIC_SOURCES:
            self.assertTrue(source.dataset_page.startswith("http"))
            self.assertTrue(source.download_url.startswith("http"))

    def test_is_probable_zip_payload_detects_zip_magic(self):
        from retail_scout.data_catalog import is_probable_zip_payload

        self.assertTrue(is_probable_zip_payload(b"PK\x03\x04rest-of-zip"))
        self.assertFalse(is_probable_zip_payload(b"<!DOCTYPE html>"))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_data_catalog -v`
Expected: FAIL with `ImportError`/`AttributeError` for `GEO_PUBLIC_SOURCES` / `is_probable_zip_payload`.

- [ ] **Step 3: Write minimal implementation**

In `retail_scout/data_catalog.py` add after `RESTAURANT_COMPETITION_SOURCES`:

```python
GEO_PUBLIC_SOURCES = [
    RawDataSource(
        source_id="taipei_districts",
        title="Taipei City administrative district boundaries (鄉鎮市區界)",
        dataset_page="https://data.gov.tw/dataset/7441",
        download_url="https://data.moi.gov.tw/MoiOD/System/DownloadFile.aspx?DATA=72874C55-884D-4CEA-B7D6-F60B0BE85AB0",
        raw_filename="taipei_districts.zip",
        agency="Ministry of the Interior, Department of Land Administration",
    ),
    RawDataSource(
        source_id="land_value_by_district",
        title="Taipei City announced land value by district (公告地價/現值)",
        dataset_page="https://data.gov.tw/dataset/26859",
        download_url="https://data.taipei/api/dataset/placeholder/resource/placeholder/download",
        raw_filename="land_value_by_district.csv",
        agency="Department of Land Administration, Taipei City Government",
    ),
]


def is_probable_zip_payload(payload: bytes) -> bool:
    return payload[:4] == b"PK\x03\x04"
```

> NOTE (execution-time binding): The `download_url`s above are best-known starting points. When you run Task 9's pipeline, if a download fails, open the `dataset_page` URL, copy the current resource download link into `download_url`, and re-run. This is the single expected discovery point for external endpoints.

- [ ] **Step 4: Update the download script**

In `scripts/download_public_data.py`, change the import and `main()`:

```python
from retail_scout.data_catalog import (
    CORE_PUBLIC_SOURCES,
    GEO_PUBLIC_SOURCES,
    build_manifest,
    is_probable_csv_payload,
    is_probable_zip_payload,
)
```

Replace `download_file` and the source loop in `main()`:

```python
def download_file(url: str, output_path: Path, *, kind: str) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    request = Request(url, headers={"User-Agent": "TaipeiRetailLocationScout/0.1"})
    with urlopen(request, timeout=120) as response:
        payload = response.read()
        if kind == "csv" and not is_probable_csv_payload(payload):
            raise ValueError(f"Downloaded payload does not look like CSV: {url}")
        if kind == "zip" and not is_probable_zip_payload(payload):
            raise ValueError(f"Downloaded payload does not look like a zip: {url}")
        output_path.write_bytes(payload)
```

In `main()`, replace the loop:

```python
    for source in CORE_PUBLIC_SOURCES + GEO_PUBLIC_SOURCES:
        target = source.raw_path(RAW_DIR)
        kind = "zip" if source.raw_filename.endswith(".zip") else "csv"
        print(f"Downloading {source.source_id} -> {target}")
        download_file(source.download_url, target, kind=kind)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python3 -m unittest tests.test_data_catalog -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add retail_scout/data_catalog.py scripts/download_public_data.py tests/test_data_catalog.py
git commit -m "feat: register district-boundary and land-value raw sources"
```

---

### Task 2: Station-name normalization

**Files:**
- Create: `retail_scout/pipeline.py`
- Test: `tests/test_pipeline.py` (create)

**Interfaces:**
- Produces: `normalize_station_name(raw: str) -> str` — strips trailing MRT line-code suffixes so line-split rows collapse to one station name. Pure function, no DuckDB.
- Produces: `normalize_taipei_name(value: str) -> str` — replaces `台` with `臺` (moved from old `features.py`).

- [ ] **Step 1: Write the failing test**

Create `tests/test_pipeline.py`:

```python
import unittest

from retail_scout.pipeline import normalize_station_name, normalize_taipei_name


class StationNameTests(unittest.TestCase):
    def test_strips_single_line_suffix(self):
        self.assertEqual(normalize_station_name("中山R"), "中山")
        self.assertEqual(normalize_station_name("中山G"), "中山")

    def test_strips_multi_letter_line_suffix(self):
        self.assertEqual(normalize_station_name("台北車站BL"), "台北車站")
        self.assertEqual(normalize_station_name("台北車站R"), "台北車站")

    def test_leaves_plain_name_untouched(self):
        self.assertEqual(normalize_station_name("公館"), "公館")
        self.assertEqual(normalize_station_name("科技大樓"), "科技大樓")

    def test_normalize_taipei_name(self):
        self.assertEqual(normalize_taipei_name("台北市大安區"), "臺北市大安區")


if __name__ == "__main__":
    unittest.main()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: FAIL with `ModuleNotFoundError: retail_scout.pipeline`.

- [ ] **Step 3: Write minimal implementation**

Create `retail_scout/pipeline.py`:

```python
from __future__ import annotations

import re

# Taipei Metro line codes that appear as a suffix on station rows in the
# entries/exits dataset (e.g. 中山R, 中山G, 台北車站BL).
_LINE_SUFFIX_RE = re.compile(r"(BL|BR|[RGOY])$")


def normalize_taipei_name(value: str) -> str:
    return value.replace("台", "臺")


def normalize_station_name(raw: str) -> str:
    name = raw.strip()
    return _LINE_SUFFIX_RE.sub("", name)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retail_scout/pipeline.py tests/test_pipeline.py
git commit -m "feat: add station-name and Taipei-name normalization"
```

---

### Task 3: Stage stations from MRT entries (DuckDB SQL)

**Files:**
- Modify: `retail_scout/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `normalize_station_name` (registered as a DuckDB scalar UDF).
- Produces: `connect() -> duckdb.DuckDBPyConnection` — opens an in-memory connection, loads `spatial`, and registers the `normalize_station_name` UDF.
- Produces: `stage_stations(con, src_table: str = "raw_mrt") -> None` — reads table `src_table` with columns `統計期, 捷運站別, 進站人次, 出站人次`; keeps only rows in the max `統計期` (parsed ROC year), normalizes station names, sums 進站+出站 per station, divides by 12, and creates table `stg_stations(station_name TEXT, monthly_entries_exits DOUBLE)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
import duckdb

from retail_scout.pipeline import connect, stage_stations


class StageStationsTests(unittest.TestCase):
    def _seed_raw_mrt(self, con):
        con.execute(
            "CREATE TABLE raw_mrt (統計期 VARCHAR, 捷運站別 VARCHAR, 進站人次 BIGINT, 出站人次 BIGINT)"
        )
        con.executemany(
            "INSERT INTO raw_mrt VALUES (?, ?, ?, ?)",
            [
                ("113年", "中山R", 10, 20),
                ("114年", "中山R", 120, 240),
                ("114年", "中山G", 60, 180),
                ("114年", "一日票", 999, 999),
            ],
        )

    def test_stage_stations_merges_lines_and_keeps_latest_year(self):
        con = connect()
        self._seed_raw_mrt(con)

        stage_stations(con)
        rows = con.execute(
            "SELECT station_name, monthly_entries_exits FROM stg_stations ORDER BY station_name"
        ).fetchall()

        # 中山R(114) 120+240 + 中山G(114) 60+180 = 600; /12 = 50.0
        self.assertIn(("中山", 50.0), rows)
        # 一日票 normalizes to 一日票 (no line suffix) and is still present at this
        # stage; it is dropped later by the entrances join.
        self.assertTrue(any(name == "中山" for name, _ in rows))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: FAIL with `ImportError` for `connect`/`stage_stations`.

- [ ] **Step 3: Write minimal implementation**

Add to `retail_scout/pipeline.py`:

```python
import duckdb


def connect() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect()
    con.execute("INSTALL spatial; LOAD spatial;")
    con.create_function("normalize_station_name", normalize_station_name, ["VARCHAR"], "VARCHAR")
    con.create_function("normalize_taipei_name", normalize_taipei_name, ["VARCHAR"], "VARCHAR")
    con.create_function("parse_roc_year", _parse_roc_year, ["VARCHAR"], "INTEGER")
    return con


def _parse_roc_year(value: str) -> int:
    match = re.search(r"\d+", value or "")
    return int(match.group()) if match else -1


def stage_stations(con: duckdb.DuckDBPyConnection, src_table: str = "raw_mrt") -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_stations AS
        WITH typed AS (
            SELECT
                parse_roc_year(統計期) AS roc_year,
                normalize_station_name(捷運站別) AS station_name,
                CAST(進站人次 AS BIGINT) + CAST(出站人次 AS BIGINT) AS entries_exits
            FROM {src_table}
        ),
        latest AS (SELECT max(roc_year) AS y FROM typed)
        SELECT
            station_name,
            sum(entries_exits) / 12.0 AS monthly_entries_exits
        FROM typed, latest
        WHERE typed.roc_year = latest.y
        GROUP BY station_name
        """
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retail_scout/pipeline.py tests/test_pipeline.py
git commit -m "feat: stage MRT stations with line merge and latest-year filter"
```

---

### Task 4: Stage entrances from entrance coordinates (DuckDB SQL)

**Files:**
- Modify: `retail_scout/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Produces: `stage_entrances(con, src_table: str = "raw_entrances") -> None` — reads table `src_table` with columns `出入口名稱, 經度, 緯度`; derives `station_name` by stripping the `站出口...`/`出口...` tail from `出入口名稱` and applying `normalize_station_name`; creates `stg_entrances(station_name TEXT, lon DOUBLE, lat DOUBLE)` (one row per entrance).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
from retail_scout.pipeline import stage_entrances


class StageEntrancesTests(unittest.TestCase):
    def test_stage_entrances_extracts_station_and_coords(self):
        con = connect()
        con.execute("CREATE TABLE raw_entrances (出入口名稱 VARCHAR, 經度 DOUBLE, 緯度 DOUBLE)")
        con.executemany(
            "INSERT INTO raw_entrances VALUES (?, ?, ?)",
            [
                ("中山站出口1", 121.520, 25.052),
                ("中山站出口2", 121.521, 25.053),
                ("公館站出口1", 121.534, 25.014),
            ],
        )

        stage_entrances(con)
        rows = con.execute(
            "SELECT station_name, count(*) FROM stg_entrances GROUP BY station_name ORDER BY station_name"
        ).fetchall()

        self.assertEqual(rows, [("中山", 2), ("公館", 1)])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: FAIL with `ImportError` for `stage_entrances`.

- [ ] **Step 3: Write minimal implementation**

Add to `retail_scout/pipeline.py`:

```python
def stage_entrances(con: duckdb.DuckDBPyConnection, src_table: str = "raw_entrances") -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_entrances AS
        SELECT
            normalize_station_name(
                regexp_replace(出入口名稱, '站?(出入口|出口).*$', '')
            ) AS station_name,
            CAST(經度 AS DOUBLE) AS lon,
            CAST(緯度 AS DOUBLE) AS lat
        FROM {src_table}
        WHERE 經度 IS NOT NULL AND 緯度 IS NOT NULL
        """
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retail_scout/pipeline.py tests/test_pipeline.py
git commit -m "feat: stage MRT entrances with station-name extraction"
```

---

### Task 5: Spatial point-in-district join

**Files:**
- Modify: `retail_scout/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `stg_entrances`.
- Produces: `stage_districts(con, geojson_path: str) -> None` — reads a district boundary file via `ST_Read`, creating `stg_districts(district TEXT, geom GEOMETRY)` where `district` is the canonical `臺北市{X}區` key (built from county + town name columns, `台`→`臺` normalized). (For tests, an alternate seeder builds `stg_districts` directly from WKT.)
- Produces: `stage_station_district(con) -> None` — for each station, point-in-polygon each entrance against `stg_districts`, pick the **modal** district across the station's entrances; creates `stg_station_district(station_name TEXT, district TEXT)`. Stations with no containing district are absent (dropped).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
from retail_scout.pipeline import stage_station_district


class StationDistrictTests(unittest.TestCase):
    def _seed(self, con):
        # Two unit-square districts side by side: A = x in [0,1], B = x in [1,2].
        con.execute("CREATE TABLE stg_districts (district VARCHAR, geom GEOMETRY)")
        con.execute(
            "INSERT INTO stg_districts VALUES "
            "('臺北市A區', ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 1,0 0))')), "
            "('臺北市B區', ST_GeomFromText('POLYGON((1 0,2 0,2 1,1 1,1 0))'))"
        )
        con.execute("CREATE TABLE stg_entrances (station_name VARCHAR, lon DOUBLE, lat DOUBLE)")
        con.executemany(
            "INSERT INTO stg_entrances VALUES (?, ?, ?)",
            [
                ("StationInA", 0.5, 0.5),
                ("StationInA", 0.6, 0.4),   # both in A
                ("Border", 0.5, 0.5),       # one in A
                ("Border", 0.5, 0.5),       # one in A -> modal A
                ("Border", 1.5, 0.5),       # one in B
                ("Outside", 9.0, 9.0),      # in neither -> dropped
            ],
        )

    def test_station_district_uses_modal_and_drops_outside(self):
        con = connect()
        self._seed(con)

        stage_station_district(con)
        rows = dict(
            con.execute("SELECT station_name, district FROM stg_station_district").fetchall()
        )

        self.assertEqual(rows["StationInA"], "臺北市A區")
        self.assertEqual(rows["Border"], "臺北市A區")
        self.assertNotIn("Outside", rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: FAIL with `ImportError` for `stage_station_district`.

- [ ] **Step 3: Write minimal implementation**

Add to `retail_scout/pipeline.py`:

```python
def stage_districts(con: duckdb.DuckDBPyConnection, geojson_path: str,
                    county_field: str = "COUNTYNAME", town_field: str = "TOWNNAME") -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_districts AS
        SELECT
            normalize_taipei_name("{county_field}" || "{town_field}") AS district,
            geom
        FROM ST_Read('{geojson_path}')
        WHERE normalize_taipei_name("{county_field}") = '臺北市'
        """
    )


def stage_station_district(con: duckdb.DuckDBPyConnection) -> None:
    con.execute(
        """
        CREATE OR REPLACE TABLE stg_station_district AS
        WITH hits AS (
            SELECT e.station_name, d.district, count(*) AS n
            FROM stg_entrances e
            JOIN stg_districts d
              ON ST_Within(ST_Point(e.lon, e.lat), d.geom)
            GROUP BY e.station_name, d.district
        ),
        ranked AS (
            SELECT station_name, district,
                   row_number() OVER (
                       PARTITION BY station_name ORDER BY n DESC, district
                   ) AS rk
            FROM hits
        )
        SELECT station_name, district FROM ranked WHERE rk = 1
        """
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retail_scout/pipeline.py tests/test_pipeline.py
git commit -m "feat: spatial point-in-district join with modal assignment"
```

---

### Task 6: Stage competitor counts from the full registry

**Files:**
- Modify: `retail_scout/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Produces: `stage_competitors(con, src_table: str = "raw_registry") -> None` — reads table `src_table` with columns `商業地址, 登記狀態`; excludes inactive statuses (`歇業`,`撤銷`,`廢止`,`停業`); extracts a canonical `臺北市{X}區` district from the (Taipei-normalized) address via regex; counts active rows per district; creates `stg_competitors(district TEXT, competitor_count BIGINT)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
from retail_scout.pipeline import stage_competitors


class StageCompetitorsTests(unittest.TestCase):
    def test_counts_active_restaurants_per_district(self):
        con = connect()
        con.execute("CREATE TABLE raw_registry (商業地址 VARCHAR, 登記狀態 VARCHAR)")
        con.executemany(
            "INSERT INTO raw_registry VALUES (?, ?)",
            [
                ("臺北市大安區復興南路一段1號", "核准設立"),
                ("台北市大安區忠孝東路一段2號", "核准設立"),  # 台 -> 臺
                ("臺北市大安區仁愛路3號", "歇業／撤銷"),       # inactive
                ("臺北市中正區羅斯福路三段3號", "核准設立"),
                ("新北市板橋區中山路1號", "核准設立"),          # not Taipei
            ],
        )

        stage_competitors(con)
        rows = dict(
            con.execute("SELECT district, competitor_count FROM stg_competitors").fetchall()
        )

        self.assertEqual(rows["臺北市大安區"], 2)
        self.assertEqual(rows["臺北市中正區"], 1)
        self.assertNotIn("新北市板橋區", rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: FAIL with `ImportError` for `stage_competitors`.

- [ ] **Step 3: Write minimal implementation**

Add to `retail_scout/pipeline.py`:

```python
def stage_competitors(con: duckdb.DuckDBPyConnection, src_table: str = "raw_registry") -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_competitors AS
        SELECT
            regexp_extract(normalize_taipei_name(商業地址), '臺北市..區') AS district,
            count(*) AS competitor_count
        FROM {src_table}
        WHERE NOT regexp_matches(登記狀態, '歇業|撤銷|廢止|停業')
          AND regexp_extract(normalize_taipei_name(商業地址), '臺北市..區') <> ''
        GROUP BY district
        """
    )
```

> NOTE: `臺北市..區` matches the two characters between `臺北市` and `區` (e.g. 大安, 中正, 中山, 士林 are all 2 chars). Taipei City's 12 districts are all two-character names, so this is exact for the in-scope geography.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retail_scout/pipeline.py tests/test_pipeline.py
git commit -m "feat: stage competitor counts from full restaurant registry"
```

---

### Task 7: Stage population and land-value cost index

**Files:**
- Modify: `retail_scout/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Produces: `stage_population(con, src_table: str = "raw_population", start_age: int = 20, end_age: int = 44) -> None` — reads `區域別` plus `{age}歲-男`/`{age}歲-女` columns; filters to Taipei (`區域別` starts with `臺北市`/`台北市`); sums residents aged 20–44 per district; creates `stg_population(district TEXT, target_population BIGINT)`. District key normalized to `臺北市{X}區`.
- Produces: `stage_cost(con, src_table: str = "raw_land_value", value_field: str = "land_value", district_field: str = "district") -> None` — averages the land value per district, then min-max scales the per-district means into **[50, 100]** as `real_estate_cost_index`; creates `stg_cost(district TEXT, real_estate_cost_index DOUBLE)`.

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
from retail_scout.pipeline import stage_cost, stage_population


class StagePopulationCostTests(unittest.TestCase):
    def test_population_sums_target_ages_for_taipei(self):
        con = connect()
        con.execute(
            'CREATE TABLE raw_population (區域別 VARCHAR, "20歲-男" BIGINT, "20歲-女" BIGINT, "44歲-男" BIGINT, "44歲-女" BIGINT)'
        )
        con.executemany(
            "INSERT INTO raw_population VALUES (?, ?, ?, ?, ?)",
            [
                ("臺北市大安區", 10, 12, 7, 9),
                ("台北市中正區", 1, 1, 1, 1),     # 台 -> 臺
                ("新北市板橋區", 100, 100, 100, 100),  # excluded
            ],
        )

        stage_population(con, start_age=20, end_age=44)
        rows = dict(
            con.execute("SELECT district, target_population FROM stg_population").fetchall()
        )

        self.assertEqual(rows["臺北市大安區"], 38)
        self.assertEqual(rows["臺北市中正區"], 4)
        self.assertNotIn("新北市板橋區", rows)

    def test_cost_index_minmax_scaled_to_50_100(self):
        con = connect()
        con.execute("CREATE TABLE raw_land_value (district VARCHAR, land_value DOUBLE)")
        con.executemany(
            "INSERT INTO raw_land_value VALUES (?, ?)",
            [("臺北市大安區", 200.0), ("臺北市中正區", 100.0), ("臺北市士林區", 50.0)],
        )

        stage_cost(con)
        rows = dict(
            con.execute("SELECT district, real_estate_cost_index FROM stg_cost ORDER BY district").fetchall()
        )

        self.assertAlmostEqual(rows["臺北市大安區"], 100.0)  # max
        self.assertAlmostEqual(rows["臺北市士林區"], 50.0)   # min
        self.assertAlmostEqual(rows["臺北市中正區"], 50.0 + 50.0 * ((100 - 50) / (200 - 50)))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: FAIL with `ImportError` for `stage_population`/`stage_cost`.

- [ ] **Step 3: Write minimal implementation**

Add to `retail_scout/pipeline.py`:

```python
def stage_population(con: duckdb.DuckDBPyConnection, src_table: str = "raw_population",
                     start_age: int = 20, end_age: int = 44) -> None:
    age_terms = " + ".join(
        f'COALESCE(CAST("{age}歲-男" AS BIGINT), 0) + COALESCE(CAST("{age}歲-女" AS BIGINT), 0)'
        for age in range(start_age, end_age + 1)
    )
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_population AS
        SELECT
            normalize_taipei_name(區域別) AS district,
            sum({age_terms}) AS target_population
        FROM {src_table}
        WHERE normalize_taipei_name(區域別) LIKE '臺北市%'
        GROUP BY district
        """
    )


def stage_cost(con: duckdb.DuckDBPyConnection, src_table: str = "raw_land_value",
               value_field: str = "land_value", district_field: str = "district") -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_cost AS
        WITH means AS (
            SELECT normalize_taipei_name("{district_field}") AS district,
                   avg(CAST("{value_field}" AS DOUBLE)) AS v
            FROM {src_table}
            GROUP BY district
        ),
        bounds AS (SELECT min(v) AS lo, max(v) AS hi FROM means)
        SELECT
            m.district,
            CASE WHEN b.hi = b.lo THEN 75.0
                 ELSE 50.0 + 50.0 * (m.v - b.lo) / (b.hi - b.lo) END AS real_estate_cost_index
        FROM means m, bounds b
        """
    )
```

> NOTE: `區域別` in the population file is the district level (e.g. `臺北市大安區`); the village column `村里` is ignored. If the real file has rows only at village granularity, group still collapses to district correctly because `區域別` repeats per village.

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retail_scout/pipeline.py tests/test_pipeline.py
git commit -m "feat: stage population and min-max-scaled land-value cost index"
```

---

### Task 8: Build the feature mart (join + transport index + scope drop)

**Files:**
- Modify: `retail_scout/pipeline.py`
- Test: `tests/test_pipeline.py`

**Interfaces:**
- Consumes: `stg_stations`, `stg_entrances`, `stg_station_district`, `stg_competitors`, `stg_population`, `stg_cost`.
- Produces: `build_feature_mart(con) -> int` — joins all staging tables into table `mart_station_features` with the five canonical feature columns; `transport_access_index` = per-station entrance count ÷ max entrance count; INNER joins on district-backed tables so any station without a resolved district / population / cost is dropped. Returns the number of dropped stations (stations present in `stg_stations` but absent from the mart).

- [ ] **Step 1: Write the failing test**

Add to `tests/test_pipeline.py`:

```python
from retail_scout.pipeline import build_feature_mart


class FeatureMartTests(unittest.TestCase):
    def test_mart_joins_and_drops_unresolved(self):
        con = connect()
        con.execute("CREATE TABLE stg_stations (station_name VARCHAR, monthly_entries_exits DOUBLE)")
        con.executemany("INSERT INTO stg_stations VALUES (?, ?)",
                        [("A", 100.0), ("B", 50.0), ("Ghost", 10.0)])
        con.execute("CREATE TABLE stg_entrances (station_name VARCHAR, lon DOUBLE, lat DOUBLE)")
        con.executemany("INSERT INTO stg_entrances VALUES (?, ?, ?)",
                        [("A", 0, 0), ("A", 0, 0), ("B", 0, 0)])  # A:2 entrances, B:1
        con.execute("CREATE TABLE stg_station_district (station_name VARCHAR, district VARCHAR)")
        con.executemany("INSERT INTO stg_station_district VALUES (?, ?)",
                        [("A", "臺北市大安區"), ("B", "臺北市中正區")])  # Ghost unresolved
        con.execute("CREATE TABLE stg_competitors (district VARCHAR, competitor_count BIGINT)")
        con.executemany("INSERT INTO stg_competitors VALUES (?, ?)",
                        [("臺北市大安區", 300), ("臺北市中正區", 100)])
        con.execute("CREATE TABLE stg_population (district VARCHAR, target_population BIGINT)")
        con.executemany("INSERT INTO stg_population VALUES (?, ?)",
                        [("臺北市大安區", 40000), ("臺北市中正區", 30000)])
        con.execute("CREATE TABLE stg_cost (district VARCHAR, real_estate_cost_index DOUBLE)")
        con.executemany("INSERT INTO stg_cost VALUES (?, ?)",
                        [("臺北市大安區", 100.0), ("臺北市中正區", 60.0)])

        dropped = build_feature_mart(con)
        rows = con.execute(
            "SELECT station_name, monthly_entries_exits, target_population, competitor_count, "
            "real_estate_cost_index, transport_access_index FROM mart_station_features "
            "ORDER BY station_name"
        ).fetchall()

        self.assertEqual(dropped, 1)  # Ghost dropped
        self.assertEqual(
            rows,
            [
                ("A", 100.0, 40000, 300, 100.0, 1.0),   # 2 entrances -> max -> 1.0
                ("B", 50.0, 30000, 100, 60.0, 0.5),     # 1 entrance -> 0.5
            ],
        )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: FAIL with `ImportError` for `build_feature_mart`.

- [ ] **Step 3: Write minimal implementation**

Add to `retail_scout/pipeline.py`:

```python
def build_feature_mart(con: duckdb.DuckDBPyConnection) -> int:
    con.execute(
        """
        CREATE OR REPLACE TABLE mart_station_features AS
        WITH entrance_counts AS (
            SELECT station_name, count(*) AS n FROM stg_entrances GROUP BY station_name
        ),
        max_entrances AS (SELECT max(n) AS mx FROM entrance_counts)
        SELECT
            s.station_name,
            round(s.monthly_entries_exits, 2) AS monthly_entries_exits,
            p.target_population,
            c.competitor_count,
            k.real_estate_cost_index,
            round(ec.n::DOUBLE / m.mx, 2) AS transport_access_index
        FROM stg_stations s
        JOIN stg_station_district sd ON s.station_name = sd.station_name
        JOIN stg_population p ON sd.district = p.district
        JOIN stg_competitors c ON sd.district = c.district
        JOIN stg_cost k ON sd.district = k.district
        JOIN entrance_counts ec ON s.station_name = ec.station_name
        CROSS JOIN max_entrances m
        ORDER BY s.station_name
        """
    )
    total = con.execute("SELECT count(*) FROM stg_stations").fetchone()[0]
    kept = con.execute("SELECT count(*) FROM mart_station_features").fetchone()[0]
    return total - kept
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python3 -m unittest tests.test_pipeline -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add retail_scout/pipeline.py tests/test_pipeline.py
git commit -m "feat: build feature mart with transport index and scope drop"
```

---

### Task 9: Rewire the scripts end-to-end; delete the hardcoded path

**Files:**
- Rewrite: `scripts/build_station_features.py`
- Rewrite: `scripts/build_competitor_summary.py`
- Modify: `scripts/run_scoring.py`
- Modify: `retail_scout/pipeline.py` (add `run_full_pipeline`)
- Delete: `retail_scout/features.py`
- Delete: `tests/test_features.py` (logic replaced by `tests/test_pipeline.py`)
- Test: `tests/test_run_scoring_script.py`

**Interfaces:**
- Consumes: all `stage_*` + `build_feature_mart`.
- Produces: `run_full_pipeline(con, *, mrt_csv, entrances_csv, population_csv, registry_csv, districts_geo, land_value_csv) -> int` — registers each raw CSV as a `raw_*` table via `read_csv_auto`, calls every stage in order, builds the mart, returns dropped count.
- Produces: `export_table(con, table: str, parquet_path: Path, csv_path: Path) -> None`.
- Produces: `run_scoring.py` writing both `station_scores.parquet` and `station_scores.csv`.

- [ ] **Step 1: Write the failing test (script I/O contract)**

Add to `tests/test_run_scoring_script.py`:

```python
    def test_write_scores_writes_parquet_and_csv(self):
        import duckdb
        from scripts.run_scoring import write_scores_parquet

        with tempfile.TemporaryDirectory() as tmp:
            rows = [{
                "station_name": "X", "monthly_entries_exits": 1.0, "target_population": 2.0,
                "competitor_count": 3.0, "real_estate_cost_index": 60.0, "transport_access_index": 0.5,
                "accessible_demand": 1.0, "competition_adjusted_customers": 1.0,
                "estimated_monthly_revenue": 1.0, "estimated_gross_profit": 1.0,
                "operating_cost_proxy": 1.0, "feasibility_ratio": 1.0,
                "economic_opportunity_index": 1.0, "profit_gap_proxy": 1.0,
                "break_even_capture_rate": 1.0, "location_score": 1.0,
                "recommendation_reason": "ok",
            }]
            pq = Path(tmp) / "s.parquet"
            csv_path = Path(tmp) / "s.csv"
            write_scores_parquet(pq, csv_path, rows)
            self.assertTrue(pq.exists())
            self.assertTrue(csv_path.exists())
            n = duckdb.connect().execute(f"SELECT count(*) FROM '{pq}'").fetchone()[0]
            self.assertEqual(n, 1)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python3 -m unittest tests.test_run_scoring_script -v`
Expected: FAIL with `ImportError` for `write_scores_parquet`.

- [ ] **Step 3: Add `run_full_pipeline` and `export_table` to `pipeline.py`**

```python
from pathlib import Path


def export_table(con: duckdb.DuckDBPyConnection, table: str,
                 parquet_path: Path, csv_path: Path) -> None:
    parquet_path.parent.mkdir(parents=True, exist_ok=True)
    con.execute(f"COPY {table} TO '{parquet_path}' (FORMAT PARQUET)")
    con.execute(f"COPY {table} TO '{csv_path}' (FORMAT CSV, HEADER)")


def run_full_pipeline(con: duckdb.DuckDBPyConnection, *, mrt_csv: Path, entrances_csv: Path,
                      population_csv: Path, registry_csv: Path, districts_geo: Path,
                      land_value_csv: Path) -> int:
    con.execute(f"CREATE TABLE raw_mrt AS SELECT * FROM read_csv_auto('{mrt_csv}', header=true)")
    con.execute(f"CREATE TABLE raw_entrances AS SELECT * FROM read_csv_auto('{entrances_csv}', header=true)")
    con.execute(f"CREATE TABLE raw_population AS SELECT * FROM read_csv_auto('{population_csv}', header=true)")
    con.execute(f"CREATE TABLE raw_registry AS SELECT * FROM read_csv_auto('{registry_csv}', header=true)")
    con.execute(f"CREATE TABLE raw_land_value AS SELECT * FROM read_csv_auto('{land_value_csv}', header=true)")
    stage_stations(con)
    stage_entrances(con)
    stage_districts(con, str(districts_geo))
    stage_station_district(con)
    stage_competitors(con)
    stage_population(con)
    stage_cost(con)
    return build_feature_mart(con)
```

- [ ] **Step 4: Rewrite `scripts/build_competitor_summary.py`**

Replace the whole file body's `main()` to use DuckDB on the downloaded registry and write the same `competitor_counts_by_district.csv` shape (keeps the README pipeline stage meaningful):

```python
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
```

- [ ] **Step 5: Rewrite `scripts/build_station_features.py`**

```python
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from retail_scout.pipeline import connect, export_table, run_full_pipeline

RAW_DIR = ROOT / "data" / "raw"
PROCESSED_DIR = ROOT / "data" / "processed"


def main() -> None:
    con = connect()
    dropped = run_full_pipeline(
        con,
        mrt_csv=RAW_DIR / "mrt_station_entries.csv",
        entrances_csv=RAW_DIR / "mrt_entrances.csv",
        population_csv=RAW_DIR / "population_by_village.csv",
        registry_csv=RAW_DIR / "restaurant_businesses.csv",
        districts_geo=RAW_DIR / "taipei_districts.zip",
        land_value_csv=RAW_DIR / "land_value_by_district.csv",
    )
    export_table(
        con, "mart_station_features",
        PROCESSED_DIR / "station_features.parquet",
        PROCESSED_DIR / "station_features.csv",
    )
    kept = con.execute("SELECT count(*) FROM mart_station_features").fetchone()[0]
    print(f"Wrote {kept} station feature rows; dropped {dropped} out-of-scope stations.")


if __name__ == "__main__":
    main()
```

> NOTE: `ST_Read` reads a shapefile inside a zip via `/vsizip/`. If `stage_districts` cannot open `taipei_districts.zip` directly, change `districts_geo` to the unzipped `.shp` path, or prefix with `/vsizip/`. Verify the shapefile's county/town field names match `COUNTYNAME`/`TOWNNAME` (MOI standard); if not, pass the real names to `stage_districts`.

- [ ] **Step 6: Add `write_scores_parquet` to `scripts/run_scoring.py` and update `main()`**

Keep existing `write_scores` (CSV). Add:

```python
def write_scores_parquet(parquet_path: Path, csv_path: Path, rows: list[dict[str, object]]) -> None:
    import duckdb

    write_scores(csv_path, rows)  # reuse CSV writer
    con = duckdb.connect()
    con.execute(f"COPY (SELECT * FROM read_csv_auto('{csv_path}', header=true)) TO '{parquet_path}' (FORMAT PARQUET)")
```

Update `main()` to also read Parquet feature input if present and write Parquet scores:

```python
def main() -> None:
    input_path = choose_feature_input_path(
        processed_path=PROCESSED_INPUT_PATH, sample_path=SAMPLE_INPUT_PATH,
    )
    rows = load_feature_rows(input_path)
    scored_rows = compute_location_scores(rows)
    write_scores_parquet(
        ROOT / "data" / "processed" / "station_scores.parquet", OUTPUT_PATH, scored_rows,
    )
    print(f"Read feature rows from {input_path}")
    print(f"Wrote {len(scored_rows)} scored station rows to {OUTPUT_PATH}")
```

- [ ] **Step 7: Delete the obsolete module and test**

```bash
git rm retail_scout/features.py tests/test_features.py
```

- [ ] **Step 8: Run the full test suite**

Run: `python3 -m unittest discover -s tests -v`
Expected: PASS (no remaining import of `retail_scout.features`). If any test still imports it, update that import to `retail_scout.pipeline`.

- [ ] **Step 9: Commit**

```bash
git add -A
git commit -m "feat: wire DuckDB pipeline into scripts; remove hardcoded station path"
```

---

### Task 10: Update docs to match the implemented system

**Files:**
- Modify: `docs/architecture.md`
- Modify: `docs/data_sources.md`
- Modify: `README.md`
- Modify: `docs/demand_evidence.md`

**Interfaces:** none (documentation).

- [ ] **Step 1: Update `docs/architecture.md`**

Replace the "Current Architecture" mermaid block so it shows the real flow: raw CSV/shapefile → DuckDB SQL staging (Parquet) → spatial join → feature mart (Parquet+CSV) → scoring → scores (Parquet+CSV) → dashboard. Add one line stating DuckDB + Parquet + the `spatial` extension are the engine, and that walking-radius competition / New Taipei / persistent DB remain future work.

- [ ] **Step 2: Update `docs/data_sources.md`**

Add table rows for the two new sources (`taipei_districts`, `land_value_by_district`) with agency, dataset page, license, and how each is used (spatial join; cost index). Note the land-value index is min-max scaled to [50,100].

- [ ] **Step 3: Update `README.md`**

In the pipeline table and Data Sources section: add the two new datasets; change outputs to `station_features.{parquet,csv}` and `station_scores.{parquet,csv}`; state the scope is **all Taipei City MRT stations** (not six demo areas); note DuckDB + Parquet as the processing layer. Remove the "Current demo trade areas" six-station list (replace with "all Taipei City stations resolved by the spatial join").

- [ ] **Step 4: Regenerate the station tables (after a real pipeline run)**

After running the full pipeline once (`download_public_data.py` → `build_competitor_summary.py` → `build_station_features.py` → `run_scoring.py`), regenerate the ranked-station tables in `README.md` ("Current score output") and `docs/demand_evidence.md` (Evidence 3 + Evidence 4) **from the actual new output CSVs** — do not hand-invent numbers. If the pipeline cannot be run (endpoint down), add a one-line note that the tables reflect the previous six-station run and must be regenerated, and leave the numbers untouched rather than fabricating.

- [ ] **Step 5: Commit**

```bash
git add docs/architecture.md docs/data_sources.md README.md docs/demand_evidence.md
git commit -m "docs: update architecture, sources, and README for DuckDB pipeline"
```

---

## Self-Review Notes

- **Spec coverage:** medallion/Parquet (Tasks 3–9), all Taipei City stations + auto-drop logging (Tasks 5, 8, 9), station normalization (Tasks 2–4), spatial join (Task 5), full-registry competitors (Task 6), land-value cost proxy scaled to model range (Task 7), scoring unchanged + Parquet/CSV outputs (Task 9), dashboard untouched (verified by leaving `station_scores.csv` contract intact), TDD with synthetic fixtures (every task), docs (Task 10). Two new ingested datasets (Task 1).
- **Known execution-time discovery points (unavoidable, external):** (1) the two new dataset download URLs (Task 1 note); (2) the district shapefile county/town field names and zip/`/vsizip/` access (Task 5 / Task 9 notes); (3) the land-value file's value/district column names (passed as params to `stage_cost`). All other logic is exact and tested on synthetic fixtures.
- **Type consistency:** canonical district key `臺北市{X}區` and the five mart columns are used identically across Tasks 5–9. `stage_*` create tables consumed by `build_feature_mart`; `run_full_pipeline` calls them in dependency order.
