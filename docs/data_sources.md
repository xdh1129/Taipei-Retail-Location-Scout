# Data Sources and Collection Plan

This project uses public, reproducible sources first. The current implementation starts with station-level aggregation and can add exact geospatial joins as the product matures.

| Source | Use | Link | Required Fields | Collection Method | Initial Fallback |
| --- | --- | --- | --- | --- | --- |
| Restaurant business registrations | Competitor density and food-service activity | https://data.gov.tw/dataset/108355 | business name, address, registration status | Download CSV from data.gov.tw and filter food/beverage categories | Use OpenStreetMap POI counts around MRT stations |
| Business registration basic data | Broader retail activity and business evidence | https://data.gov.tw/dataset/44710 | business id, name, address, status | Use the official API or CSV resources listed on the dataset page | Use only restaurant registration data |
| Village household and single-age population | Target customer base by age group | https://data.gov.tw/dataset/77132 | month, district code, district, village, households, population, age columns | Use the RIS API path documented on the dataset page for the latest month | Aggregate by district instead of village |
| Taipei MRT hourly entry/exit flow | Foot-traffic proxy | https://data.gov.tw/dataset/128506 | year, month, URL to monthly OD data | Download the monthly CSV resources and aggregate station entries/exits | Use yearly station entry/exit dataset |
| Taipei MRT station entry/exit totals | Simpler foot-traffic proxy | https://data.gov.tw/dataset/133184 | period, station, entries, exits | Download CSV and aggregate recent periods | Use this instead of hourly OD data |
| Taipei MRT entrance coordinates | Trade-area center points | https://data.gov.tw/en/datasets/128428 | entrance name, longitude, latitude, accessibility flag | Download CSV and group entrances by station | Manually seed coordinates for 6-10 demo stations |
| Village boundary map | Spatial join from population to trade areas | https://data.gov.tw/en/datasets/7438 | village code, county, town, village name, geometry | Download SHP and join with population table | Use district-level population without polygons |
| Taipei city village boundary map | Smaller Taipei-only spatial join | https://data.taipei/dataset/detail?id=6b17b31d-4e16-495e-95b1-9fd1f47c80d8 | village name, district, geometry | Download SHP from Taipei Open Data | Use national village boundary map |
| Real-price registration batch data | Real-estate cost proxy | https://data.gov.tw/dataset/25119 | transaction area, transaction date, unit price | Download ZIP/CSV from the MOI real-price open data page | Use district-level cost index from a manually prepared sample table |
| Taiwan township/district boundaries (current, MOI-derived TopoJSON) | District polygons for the spatial station-to-district join | https://github.com/dkaoster/taiwan-atlas (jsDelivr CDN) | `COUNTYNAME`, `TOWNNAME`, geometry | Download the TopoJSON and load with DuckDB `ST_Read`; filter to `臺北市` | Authoritative MOI SHP from data.gov.tw dataset 7441 (the direct download endpoint was unreachable at build time) |
| District land value (real-estate cost index input) | Cost pressure for the scoring model | Bundled stand-in: `data/reference/land_value_by_district.csv` | `district`, `land_value` | Read the bundled reference table; averaged by district in DuckDB and min-max scaled to `[50, 100]` | Replace with a per-district aggregate of the government 公告地價/現值 dataset (data.gov.tw dataset 26859) once a clean endpoint is wired in |
| OpenStreetMap Overpass API | Competitor POIs and surrounding amenities | https://wiki.openstreetmap.org/wiki/Overpass_API | amenity, shop, name, lat, lon | Query cafes, restaurants, schools, offices within Taipei bounding box | Use only government business registration |
| TGOS address geocoding | Convert business addresses to coordinates | https://api.tgos.tw/TGOS_MAP_API/docs/site/web/AddrLocate | address, longitude, latitude, match type | Apply for APPId/APIKey and geocode cached addresses | Skip exact geocoding in the initial build |

## Core Public Data Inventory

Access date: 2026-06-04. The reproducible source manifest is stored at `data/raw/public_data_manifest.json`.

| Raw File | Dataset Page | Actual Download URL | License | Notes |
| --- | --- | --- | --- | --- |
| `data/raw/mrt_station_entries.csv` | https://data.gov.tw/dataset/133184 | https://tsis.dbas.gov.taipei/statis/webMain.aspx?sys=220&funid=a05023601&cycle=4&outmode=12&compmode=0&outkind=3&deflst=2&nzo=1&type=0&ymf=8500&ymt=11400&kind=21 | Open Government Data License, version 1.0 | 170 KB CSV. Columns include period, station, entries, exits, entry change rate, and exit change rate. |
| `data/raw/mrt_entrances.csv` | https://data.gov.tw/en/datasets/128428 | https://scidm.nchc.org.tw/en/dataset/best_wish128428/resource/60296981-c2e4-4766-a1e8-4ec8b4448af6/nchcproxy | Open Government Data License, version 1.0 | 18 KB CSV. Columns include entrance name, entrance id, longitude, and latitude. The direct `data.taipei` download returned HTTP 500 on 2026-06-04, so the NCHC open-data mirror is used for reproducibility. |
| `data/raw/population_by_village.csv` | https://data.gov.tw/dataset/77132 | https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/2C7688CB-B505-4D00-B11C-66C4D31B024F/resource/44EDEF1F-EBDC-4CF0-9C6D-E845875CECF1/download | Open Government Data License, version 1.0 | 4.2 MB CSV for `11504` with village code, area, village name, households, total population, sex totals, and single-age population columns. |
| `data/raw/taipei_districts.json` | https://github.com/dkaoster/taiwan-atlas | https://cdn.jsdelivr.net/npm/taiwan-atlas@2021.9.20/towns-10t.json | MIT (taiwan-atlas packaging); source boundaries Open Government Data License | Current Taiwan township/district boundaries (MOI-derived), packaged as TopoJSON by `taiwan-atlas` and served via jsDelivr. Read directly by DuckDB `ST_Read` (already exposes `COUNTYNAME`/`TOWNNAME`), filtered to `臺北市` district polygons for the spatial point-in-district join. The authoritative MOI SHP (dataset 7441) is preferred but its direct download endpoint was unreachable at build time. |
| `data/reference/land_value_by_district.csv` (bundled stand-in) | https://data.gov.tw/dataset/26859 | n/a — bundled in repo, not downloaded | Reference table maintained in-repo | **Transparent stand-in**, not a live dataset. Small district-level table of relative Taipei City announced land value; averaged by district in DuckDB and min-max scaled to `[50, 100]` to produce `real_estate_cost_index`. Only relative ordering affects the score. See `data/reference/README.md`; replace with a real 公告地價/現值 per-district aggregate for production. |

The download script is:

```bash
python3 scripts/download_public_data.py
```

It rejects obvious HTML error pages before writing files, because one stale population URL returned a small HTML page during collection.

## Processed Competitor and Feature Data Inventory

Access date: 2026-06-04. The competitor source manifest is stored at `data/processed/competitor_summary_manifest.json`.

| Output File | Input Source | Method | Notes |
| --- | --- | --- | --- |
| `data/processed/competitor_counts_by_district.csv` | https://data.gov.tw/dataset/108355 | Load the full official restaurant business registration CSV into DuckDB and count active businesses per district with `retail_scout.pipeline.stage_competitors`. | The full registry (whole file, not a 4-district subset) is staged and aggregated entirely inside DuckDB. |
| `data/processed/station_features.parquet` and `.csv` | Core MRT, entrance, district-boundary, population, land-value, and competitor sources | Run the DuckDB medallion pipeline in `retail_scout/pipeline.py` via `scripts/build_station_features.py`: stage each raw source as SQL, spatially join entrances to districts, then build the feature mart for every Taipei City MRT station. | Required columns: station name, monthly entries/exits, target population, competitor count, cost index, transport access index. Stations whose entrances fall outside Taipei City district polygons are dropped; the drop count is logged. |
| `data/processed/station_scores.parquet` and `.csv` | `data/processed/station_features.csv` | Run risk-adjusted economic opportunity scoring with `scripts/run_scoring.py`. | The scoring script prefers processed features when present and falls back to bundled sample data otherwise. The dashboard reads the CSV. |

Feature definitions:

- `monthly_entries_exits`: latest numeric ROC year in the MRT station entry/exit dataset, summed across configured line-specific station names, divided by 12.
- `target_population`: residents aged 20-44 in the station's resolved district.
- `competitor_count`: active restaurant business registrations in the station's resolved district, counted from the full registry in DuckDB.
- `real_estate_cost_index`: district-level mean announced land value (公告地價/現值), min-max scaled into the `[50, 100]` range, computed in `retail_scout.pipeline.stage_cost`.
- `transport_access_index`: station entrance count normalized within all resolved Taipei City stations.

## Demand Evidence Without Interviews

Use public evidence in product and go-to-market materials:

- Competitor products exist, such as retail location intelligence and site-selection tools.
- Existing site-selection tools use subscription or report-based pricing.
- Opening a retail store has high fixed costs, so reducing bad-location risk has economic value.
- Public restaurant registration counts show active competition and frequent business formation.

## Data Ethics and Risks

- Avoid scraping Google Maps, 591, or other platforms with restrictive terms.
- Attribute OpenStreetMap if OSM-derived POIs or map layers are used.
- Cache geocoding results and respect rate limits.
- State clearly that real-estate transaction data is a proxy, not actual retail rent.
