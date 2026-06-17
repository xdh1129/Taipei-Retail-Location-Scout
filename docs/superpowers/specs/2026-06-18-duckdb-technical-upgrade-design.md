# Technical Upgrade: DuckDB Medallion Pipeline for All Taipei City MRT Stations

Date: 2026-06-18
Status: Approved design (pre-implementation)

## Goal

Upgrade the Taipei Retail Location Scout processing layer from a hardcoded,
six-station, pure-Python (`csv` module) prototype into a credible-scale,
data-driven pipeline that processes the **full** public datasets with a real
columnar/SQL engine (DuckDB) and scores **all Taipei City MRT stations**.

This directly strengthens the course's 40%-weighted "technical system design and
implementation quality" criterion by making the implementation match the
architecture the project already claims, on the real scale and shape of the data,
runnable on a laptop.

### Optimization target

Credible scale on real data — process the actual full datasets honestly, not
big-data-paradigm theater. DuckDB over local files is "the right tool for the
scale and shape of the data," defensible in the report.

## Scope

In scope:

- DuckDB-driven medallion pipeline over files (raw CSV/SHP -> Parquet staging ->
  Parquet + CSV mart -> scores).
- All **Taipei City** MRT stations (~80), data-driven, replacing the hardcoded
  six-station `DEMO_STATIONS` path.
- Station-name normalization (line-suffix merge, non-station removal).
- Spatial point-in-district join (entrance coordinates -> district polygon).
- Full restaurant-registry competitor counting (entire file, not 4 districts).
- Land-value-derived `real_estate_cost_index` replacing the hand-typed values.
- Two new ingested datasets: Taipei district boundaries + public land value.
- TDD throughout, with small synthetic fixtures.

Explicitly out of scope (YAGNI — documented as future work, not code):

- Walking-radius / geocoded per-station competitor counts.
- New Taipei City stations.
- Persistent `.duckdb` database store (file-based Parquet only).
- Spark, message queues, object storage, 10x/100x infrastructure.
- Dashboard changes, including the pydeck station map.

## Geographic scope decision

The MRT entries dataset spans both Taipei City and New Taipei (e.g. 三重, 中和,
頂埔). This iteration deliberately restricts to **Taipei City only** for clean
boundary / population / land-value coverage (~12 districts). The spatial join
enforces this: any station whose entrances fall outside the Taipei City district
polygons is dropped. The dropped station count is logged and reported, so coverage
is data-driven and never silently wrong.

## Architecture & data flow (medallion over files)

```
RAW (data/raw/, as-downloaded, immutable)
  mrt_station_entries.csv         (existing)
  mrt_entrances.csv  (經度/緯度)   (existing)
  population_by_village.csv        (existing)
  restaurant_businesses.csv        (full registry, downloaded; large, git-ignored)
  taipei_districts.{shp|geojson}   (NEW — district boundaries)
  land_value_by_district.csv       (NEW — 公告地價/現值 cost proxy)

        │  DuckDB SQL transforms (one engine; reads CSV/SHP, writes Parquet)
        ▼
STAGING (data/processed/staging/*.parquet — cleaned, typed, normalized)
  stations             (de-duped, line-suffix-merged, non-stations removed, latest period)
  entrances            (station_name + lon/lat + entrance_count)
  station_district     (spatial join: entrance point → district polygon)
  population_district   (residents 20–44 per district)
  competitors_district  (full registry → active count per Taipei City district)
  cost_district         (land-value index per district)

        │  DuckDB join → one row per station
        ▼
MART
  station_features.parquet + .csv   (the 5 features, now ~80 rows)

        │  scoring module (unchanged economic model)
        ▼
  station_scores.parquet + .csv     (dashboard reads CSV; CSV kept for compatibility)
```

Principles:

- DuckDB is the only processing engine. Each stage is a SQL file/function with an
  inspectable Parquet output.
- CSV outputs are retained alongside Parquet so the existing dashboard and tests
  keep working unchanged.
- Spatial join uses DuckDB's `spatial` extension (runtime `INSTALL`/`LOAD spatial`);
  geopandas/shapely (already in requirements) is the fallback if needed.

## Ingestion (two new datasets)

`scripts/download_public_data.py` and `retail_scout/data_catalog.py` gain two new
`RawDataSource` entries:

1. **District boundaries** — Taipei administrative district (鄉鎮市區界) shapefile
   or GeoJSON from data.gov.tw (MOI). Downloaded as zipped SHP/GeoJSON, unzipped
   into `data/raw/`. Drives the spatial join.
2. **Public land value (公告土地現值/地價)** — district-level CSV from data.gov.tw,
   aggregated to one cost index per Taipei City district.

Robustness:

- Each new source gets a manifest entry (dataset page URL, download URL, agency,
  license, access date).
- The download script validates payloads (reuse the `is_probable_csv_payload`
  pattern; add a zip/shapefile sniff for the boundary file) and fails loudly with
  the dataset page URL if an endpoint moved.

## Processing (DuckDB SQL transforms)

### Station normalization (staging)

- **Strip line suffixes**: trailing line codes (`R`, `G`, `BL`, `O`, `BR`, `Y`, …)
  removed so `中山G`/`中山R` -> `中山`, `台北車站BL`/`台北車站R` -> `台北車站`.
  Implemented as a documented mapping/regex; covered by tests on known cases.
- **Drop non-stations**: rows that do not appear in the entrances coordinate file
  (e.g. `一日票`, passes, totals) are dropped. The entrances file is the
  authoritative station list.
- **Latest period only**: keep `max(統計期)` rows; sum 進站人次 + 出站人次 per
  normalized station, divide by 12 for `monthly_entries_exits`.

### Joins (all DuckDB SQL)

- **`station_district`**: entrance points (lon/lat) -> point-in-polygon against the
  Taipei district shapefile. A station spanning two districts is assigned the
  **modal district of its entrances** (documented edge case).
- **`competitors_district`**: stream the full registry CSV through DuckDB; exclude
  inactive registrations (`歇業`/`撤銷`/`廢止`/`停業`, reimplemented as SQL); filter
  Taipei City addresses; `GROUP BY district`.
- **`population_district`**: residents aged 20–44 summed per district.
- **`cost_district`**: land-value index per district.
- **Final mart**: join all five on district/station -> one row per station with the
  five feature columns the scorer already expects:
  `station_name`, `monthly_entries_exits`, `target_population`, `competitor_count`,
  `real_estate_cost_index`, `transport_access_index`.

`retail_scout/features.py` Python logic is reimplemented as SQL (or thin
DuckDB-calling functions). The hardcoded `DEMO_STATIONS` list and per-station
`real_estate_cost_index` constants are removed; cost now comes from the land-value
join.

## Scoring & outputs (mostly unchanged)

- `retail_scout/scoring.py` economic model is kept as-is (transparent, tested,
  per-row — scales 6 -> ~80 for free).
- `transport_access_index` (entrance count ÷ max) re-normalizes across ~80 stations;
  this is correct and more meaningful, but absolute scores shift — documented.
- `scripts/run_scoring.py` reads the new mart (Parquet or CSV) and writes
  `station_scores.parquet` + `station_scores.csv`. The dashboard still reads
  `station_scores.csv`, so no dashboard code change (backbone-only scope holds).

## Testing (TDD)

New / updated tests, using small synthetic in-memory fixtures (not the real
multi-MB files), keeping the suite fast:

- **Station normalization** — line-suffix stripping (`中山G`->`中山`), non-station
  removal (`一日票` dropped), known multi-line merges.
- **Spatial join** — tiny fixture (2–3 fake district polygons + points) asserting
  correct point-in-district assignment, including the multi-district modal edge case.
- **Competitor aggregation** — small in-memory registry fixture -> correct
  active-count-per-district, asserting inactive statuses excluded.
- **Coverage/scope** — a station outside Taipei polygons is dropped and counted.
- **Feature-mart integration** — fixtures through the full DuckDB pipeline produce
  the five expected columns and expected row count.
- **Existing tests** — `test_scoring.py` stays green (model unchanged);
  `test_features.py` rewritten against the SQL pipeline;
  `test_dashboard.py` / `test_run_scoring_script.py` updated for new I/O.

## Dependencies, reproducibility & docs

- **Dependencies**: `requirements.txt` already lists `duckdb`, `geopandas`,
  `shapely`, `pyproj` — likely no new packages. Add the DuckDB `spatial` extension
  load at runtime. Add a package only if boundary parsing requires it. Must run via
  `pip install -r requirements.txt` on a laptop.
- **Pipeline commands** keep the same shape
  (`download_public_data` -> `build_competitor_summary` -> `build_station_features`
  -> `run_scoring`), so the README "Full Reproduction Pipeline" table still
  describes reality. Update outputs (Parquet + CSV), new datasets, Taipei-City scope.
- **Docs**: update `docs/architecture.md` "Current Architecture" diagram to the real
  medallion/DuckDB/Parquet flow (no longer aspirational); add boundary + land-value
  entries to `docs/data_sources.md`; regenerate the station tables in README and
  `docs/demand_evidence.md` **from the new ~80-station output after the pipeline
  runs** (numbers change; not hand-edited).

## Success criteria

- `python3 scripts/...` full pipeline runs end-to-end on a laptop from
  `pip install -r requirements.txt`, producing `station_scores.{parquet,csv}` for all
  resolved Taipei City stations.
- Processing is performed by DuckDB SQL over the full raw datasets (full restaurant
  registry, full population file), not the Python `csv` module on a 4-district subset.
- No hardcoded station list or hand-typed cost index remains.
- Dropped (out-of-scope) station count is logged.
- All tests pass; suite stays fast (synthetic fixtures).
- README / architecture / data-sources docs match the implemented system.
