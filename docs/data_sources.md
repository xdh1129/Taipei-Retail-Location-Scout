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
| OpenStreetMap Overpass API | Competitor POIs and surrounding amenities | https://wiki.openstreetmap.org/wiki/Overpass_API | amenity, shop, name, lat, lon | Query cafes, restaurants, schools, offices within Taipei bounding box | Use only government business registration |
| TGOS address geocoding | Convert business addresses to coordinates | https://api.tgos.tw/TGOS_MAP_API/docs/site/web/AddrLocate | address, longitude, latitude, match type | Apply for APPId/APIKey and geocode cached addresses | Skip exact geocoding in the initial build |

## Core Public Data Inventory

Access date: 2026-06-04. The reproducible source manifest is stored at `data/raw/public_data_manifest.json`.

| Raw File | Dataset Page | Actual Download URL | License | Notes |
| --- | --- | --- | --- | --- |
| `data/raw/mrt_station_entries.csv` | https://data.gov.tw/dataset/133184 | https://tsis.dbas.gov.taipei/statis/webMain.aspx?sys=220&funid=a05023601&cycle=4&outmode=12&compmode=0&outkind=3&deflst=2&nzo=1&type=0&ymf=8500&ymt=11400&kind=21 | Open Government Data License, version 1.0 | 170 KB CSV. Columns include period, station, entries, exits, entry change rate, and exit change rate. |
| `data/raw/mrt_entrances.csv` | https://data.gov.tw/en/datasets/128428 | https://scidm.nchc.org.tw/en/dataset/best_wish128428/resource/60296981-c2e4-4766-a1e8-4ec8b4448af6/nchcproxy | Open Government Data License, version 1.0 | 18 KB CSV. Columns include entrance name, entrance id, longitude, and latitude. The direct `data.taipei` download returned HTTP 500 on 2026-06-04, so the NCHC open-data mirror is used for reproducibility. |
| `data/raw/population_by_village.csv` | https://data.gov.tw/dataset/77132 | https://opdadm.moi.gov.tw/api/v1/no-auth/resource/api/dataset/2C7688CB-B505-4D00-B11C-66C4D31B024F/resource/44EDEF1F-EBDC-4CF0-9C6D-E845875CECF1/download | Open Government Data License, version 1.0 | 4.2 MB CSV for `11504` with village code, area, village name, households, total population, sex totals, and single-age population columns. |

The download script is:

```bash
python3 scripts/download_public_data.py
```

It rejects obvious HTML error pages before writing files, because one stale population URL returned a small HTML page during collection.

## Processed Competitor and Feature Data Inventory

Access date: 2026-06-04. The competitor source manifest is stored at `data/processed/competitor_summary_manifest.json`.

| Output File | Input Source | Method | Notes |
| --- | --- | --- | --- |
| `data/processed/competitor_counts_by_district.csv` | https://data.gov.tw/dataset/108355 | Stream the official restaurant business registration CSV and count active businesses by configured station district. | The full source CSV is about 21 MB. To avoid local disk pressure, the project stores only the reproducible district summary and manifest. |
| `data/processed/station_features.csv` | Core MRT, entrance, population files plus competitor summary | Build six station-level rows using `scripts/build_station_features.py`. | Required columns: station name, monthly entries/exits, target population, competitor count, cost proxy, transport access index. |
| `data/processed/station_scores.csv` | `data/processed/station_features.csv` | Run transparent weighted scoring with `scripts/run_scoring.py`. | The scoring script prefers processed features when present and falls back to bundled sample data otherwise. |

Feature definitions:

- `monthly_entries_exits`: latest numeric ROC year in the MRT station entry/exit dataset, summed across configured line-specific station names, divided by 12.
- `target_population`: residents aged 20-44 in the configured station district.
- `competitor_count`: active restaurant business registrations in the configured station district.
- `real_estate_cost_index`: district-level cost proxy documented in `retail_scout.features.StationConfig`.
- `transport_access_index`: station entrance count normalized within the six demo stations.

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
