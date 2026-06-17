# Taipei Retail Location Scout

Taipei Retail Location Scout is a lightweight site-selection intelligence toolkit for small retail operators in Taipei. It turns open public data about Taipei MRT foot traffic, population, restaurant competition, and cost proxies into an explainable site-attractiveness score for retail expansion decisions.

The initial customer is a small coffee, beverage, or light-meal chain evaluating Taipei MRT-adjacent trade areas. The product is designed as a first-pass screening tool, not a revenue prediction engine.

## Current Status

Implemented:

- Reproducible public-data download scripts.
- A DuckDB-driven medallion pipeline (`retail_scout/pipeline.py`) that stages raw CSV/shapefile data in SQL, resolves each station to a Taipei City district with a spatial point-in-district join, and builds a station-level feature mart.
- Transparent scoring model with tests.
- Streamlit dashboard with ranking, filtering, indicator charts, selected-area details, and CSV export.
- Demand evidence and willingness-to-pay notes for early go-to-market planning.

Scope: all Taipei City MRT stations resolved by the spatial join, not a fixed list of demo trade areas. Stations whose entrances fall outside Taipei City district polygons are dropped, and the dropped count is logged.

## Quick Start

Create an environment and install dependencies:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Run tests:

```bash
python3 -m unittest discover -s tests
```

Run the processed-data scoring step:

```bash
python3 scripts/run_scoring.py
```

Launch the dashboard:

```bash
streamlit run app/streamlit_app.py
```

If port `8501` is occupied, use another port:

```bash
streamlit run app/streamlit_app.py --server.port 8502
```

## Full Reproduction Pipeline

Run the full local pipeline from public data to dashboard-ready scores:

```bash
python3 scripts/download_public_data.py
python3 scripts/build_competitor_summary.py
python3 scripts/build_station_features.py
python3 scripts/run_scoring.py
streamlit run app/streamlit_app.py
```

Pipeline stages:

| Step | Command | Output |
| --- | --- | --- |
| Download public data | `python3 scripts/download_public_data.py` | MRT entries/exits, MRT entrance coordinates, population CSV, restaurant registry CSV, and the Taipei district boundary TopoJSON (`taipei_districts.json`) under `data/raw/` |
| Build competitor summary | `python3 scripts/build_competitor_summary.py` | `data/processed/competitor_counts_by_district.csv` |
| Build feature table | `python3 scripts/build_station_features.py` | `data/processed/station_features.parquet` and `data/processed/station_features.csv` |
| Score locations | `python3 scripts/run_scoring.py` | `data/processed/station_scores.parquet` and `data/processed/station_scores.csv` |
| Serve dashboard | `streamlit run app/streamlit_app.py` | Local browser dashboard |

The processing layer is DuckDB plus Parquet: `retail_scout/pipeline.py` stages every raw source as a SQL table inside DuckDB, performs the spatial point-in-district join with DuckDB's `spatial` extension (`ST_Read` / `ST_Within`), and writes the feature mart and scores as Parquet with a CSV export alongside. The dashboard continues to read the CSV.

Note: the restaurant registration source is about 21 MB. The full registry is now loaded into DuckDB and aggregated to district-level competitor counts entirely in SQL via `build_competitor_summary.py`, which stores only the reproducible district-level competitor summary.

## Data Sources

Primary data sources:

| Dataset | Use | Manifest / Output |
| --- | --- | --- |
| Taipei MRT station entries/exits | Foot-traffic proxy | `data/raw/mrt_station_entries.csv` |
| Taipei MRT entrance coordinates | Transport access proxy | `data/raw/mrt_entrances.csv` |
| Village household and single-age population | 20-44 target population proxy | `data/raw/population_by_village.csv` |
| Restaurant business registrations | Competitor density proxy | `data/processed/competitor_counts_by_district.csv` |
| Taiwan township/district boundaries (current, MOI-derived TopoJSON via `taiwan-atlas` on jsDelivr) | Spatial point-in-district join from MRT entrances to districts; filtered to Taipei City | `data/raw/taipei_districts.json` |
| District land value (real-estate cost index, min-max scaled to `[50, 100]`) | Cost pressure in the scoring model | **Bundled stand-in** — `data/reference/land_value_by_district.csv` (see note below) |

> **Land value is a transparent stand-in, not a live dataset.** A clean per-district open dataset of announced land value (公告地價/現值) was not available behind a working download endpoint, so the repository ships a small, documented reference table of relative Taipei City district land values at `data/reference/land_value_by_district.csv`. Because the pipeline min-max scales it into `[50, 100]`, only the relative ordering affects the score. To use real data, replace that file with a per-district aggregate of the government land-value dataset (same `district,land_value` columns); no code change is needed. Details: `data/reference/README.md`.

Source manifests:

- `data/raw/public_data_manifest.json`
- `data/processed/competitor_summary_manifest.json`

Detailed source notes are in `docs/data_sources.md`.

## Scoring Method

The scoring pipeline uses a transparent risk-adjusted economic opportunity model.
Instead of assuming that high foot traffic always wins, the model estimates how close
each trade area is to covering its demand, competition, and cost pressures.

```text
Accessible Demand =
(monthly foot traffic * 0.00065 + target population * 0.28)
* (0.85 + 0.30 * transport access index)

Competition-Adjusted Customers =
Accessible Demand / (1 + competitor count / 300) ^ 1.15

Estimated Monthly Revenue =
Competition-Adjusted Customers * 160

Estimated Gross Profit =
Estimated Monthly Revenue * 0.62

Operating Cost Proxy =
360,000 + real estate cost index * 4,500

Feasibility Ratio =
Estimated Gross Profit / Operating Cost Proxy

Profit Gap Proxy =
Estimated Gross Profit - Operating Cost Proxy

Economic Opportunity Index =
min(Feasibility Ratio, 1.0) * 100

Location Score = Economic Opportunity Index
```

Feature definitions:

- `monthly_entries_exits`: latest MRT annual entries plus exits, divided by 12.
- `target_population`: residents aged 20-44 in the station's resolved district.
- `competitor_count`: active restaurant business registrations in the station's resolved district, counted from the full registry in DuckDB.
- `real_estate_cost_index`: district-level mean announced land value, min-max scaled into `[50, 100]`.
- `transport_access_index`: station entrance count normalized within all resolved Taipei City stations.
- `feasibility_ratio`: estimated gross profit divided by operating cost proxy.
- `break_even_capture_rate`: required monthly customers divided by accessible demand.

Current score output:

```text
data/processed/station_scores.parquet
data/processed/station_scores.csv
```

**Note:** the example below reflects the previous six-station demo run and has not been regenerated against the new DuckDB pipeline. It must be regenerated from the actual new output CSV once the full Taipei City pipeline (including the district-boundary and land-value datasets) has been run against live data; do not treat these numbers as current.

At the time of the previous six-station processed run, the top-ranked trade area was `劍潭`, with a feasibility ratio above 1.0. `台北車站` remained a strong but more expensive opportunity: its high foot traffic kept the index high, while cost and competition pressure kept it below the top-ranked area.

## Dashboard

The Streamlit dashboard reads `data/processed/station_scores.csv` when available. If the processed score file does not exist, it falls back to bundled sample data.

Dashboard features:

- Top-station KPI cards.
- Economic opportunity, feasibility ratio, and break-even capture metrics.
- Minimum-score filter.
- Ranked trade-area table.
- Indicator chart.
- Selected-area detail view.
- CSV download button.

## Repository Layout

```text
retail_scout/
  data_catalog.py            Reproducible source catalog.
  dashboard.py               Dashboard data helpers.
  pipeline.py                DuckDB medallion pipeline: SQL staging, spatial join, feature mart, Parquet/CSV export.
  scoring.py                 Core location scoring logic.
scripts/
  download_public_data.py    Downloads core public datasets.
  build_competitor_summary.py Loads the full restaurant registry into DuckDB and counts competitors by district.
  build_station_features.py  Runs the DuckDB pipeline to build the station-level feature mart.
  run_scoring.py             Builds ranked station scores from a feature table.
app/
  streamlit_app.py           Streamlit dashboard entry point.
data/
  raw/                       Local raw data outputs; large CSVs are ignored by git.
  processed/                 Reproducible processed feature and score outputs (Parquet + CSV).
  sample/                    Small fallback sample data.
docs/
  architecture.md            System architecture diagrams and data flow.
  data_sources.md            Dataset inventory and collection notes.
  demand_evidence.md         Demand validation and willingness-to-pay evidence.
  report_outline.md          English product and technical narrative outline.
  superpowers/plans/         Implementation checklist.
tests/
  test_dashboard.py
  test_data_catalog.py
  test_pipeline.py
  test_run_scoring_script.py
  test_scoring.py
```

## Product Planning Materials

Use these files when writing a product brief, technical note, or external project overview:

- Architecture: `docs/architecture.md`
- Data sources: `docs/data_sources.md`
- Demand evidence: `docs/demand_evidence.md`
- Report outline: `docs/report_outline.md`
- Original implementation plan and checklist: `docs/superpowers/plans/2026-06-04-retail-location-scout.md`
- DuckDB pipeline upgrade design and plan: `docs/superpowers/specs/2026-06-18-duckdb-technical-upgrade-design.md`, `docs/superpowers/plans/2026-06-18-duckdb-technical-upgrade.md`

Any external writeup should explain that this is a first-pass location screening tool. It should not claim to predict store revenue.

## Business Model

Initial monetization hypothesis:

- NTD 990 per one-time location comparison report.
- NTD 2,990 per month for repeated screening and CSV exports.

The rationale is documented in `docs/demand_evidence.md`: the price is small relative to restaurant opening costs and comparable to lightweight site-selection products.

## Limitations

- No interviews were conducted; demand validation uses public-data evidence.
- Competition is counted at district level, not exact walking radius.
- Real-estate cost is a district-level proxy, not actual retail rent.
- The model ranks relative attractiveness among all resolved Taipei City MRT stations; it does not predict revenue.
- Coverage is limited to Taipei City; New Taipei City stations are not yet in scope.
- Future versions should add finer-grained POI/geocoding, walking-radius competition, rental data, user feedback, and validation against actual store outcomes.

## Troubleshooting

If `streamlit` is missing:

```bash
pip install -r requirements.txt
```

If `data/processed/station_scores.csv` is missing:

```bash
python3 scripts/build_station_features.py
python3 scripts/run_scoring.py
```

If competitor data fails due to disk pressure, rerun:

```bash
python3 scripts/build_competitor_summary.py
```

The script aggregates the full registry inside DuckDB and writes only a small summary file.

If public-data endpoints change, update `retail_scout/data_catalog.py` and rerun the relevant download script.
