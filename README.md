# Taipei Retail Location Scout

Taipei Retail Location Scout is a lightweight site-selection intelligence toolkit for small retail operators in Taipei. It turns open public data about Taipei MRT foot traffic, population, restaurant competition, and cost proxies into an explainable site-attractiveness score for retail expansion decisions.

The initial customer is a small coffee, beverage, or light-meal chain evaluating Taipei MRT-adjacent trade areas. The product is designed as a first-pass screening tool, not a revenue prediction engine.

## Current Status

Implemented:

- Reproducible public-data download scripts.
- Station-level feature engineering pipeline.
- Transparent scoring model with tests.
- Streamlit dashboard with ranking, filtering, indicator charts, selected-area details, and CSV export.
- Demand evidence and willingness-to-pay notes for early go-to-market planning.

Current demo trade areas:

- 台北車站
- 中山
- 公館
- 古亭
- 科技大樓
- 劍潭

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
| Download public data | `python3 scripts/download_public_data.py` | MRT entries/exits, MRT entrance coordinates, population CSVs under `data/raw/` |
| Build competitor summary | `python3 scripts/build_competitor_summary.py` | `data/processed/competitor_counts_by_district.csv` |
| Build feature table | `python3 scripts/build_station_features.py` | `data/processed/station_features.csv` |
| Score locations | `python3 scripts/run_scoring.py` | `data/processed/station_scores.csv` |
| Serve dashboard | `streamlit run app/streamlit_app.py` | Local browser dashboard |

Note: the restaurant registration source is about 21 MB. To avoid local disk pressure, `build_competitor_summary.py` streams the official CSV and stores only the reproducible district-level competitor summary.

## Data Sources

Primary data sources:

| Dataset | Use | Manifest / Output |
| --- | --- | --- |
| Taipei MRT station entries/exits | Foot-traffic proxy | `data/raw/mrt_station_entries.csv` |
| Taipei MRT entrance coordinates | Transport access proxy | `data/raw/mrt_entrances.csv` |
| Village household and single-age population | 20-44 target population proxy | `data/raw/population_by_village.csv` |
| Restaurant business registrations | Competitor density proxy | `data/processed/competitor_counts_by_district.csv` |

Source manifests:

- `data/raw/public_data_manifest.json`
- `data/processed/competitor_summary_manifest.json`

Detailed source notes are in `docs/data_sources.md`.

## Scoring Method

The scoring pipeline computes a transparent `Location Score`:

```text
Location Score =
0.30 * normalized foot traffic
+ 0.25 * normalized target population
+ 0.20 * normalized demand-to-competition gap
+ 0.15 * normalized cost affordability
+ 0.10 * normalized transport access
```

Feature definitions:

- `monthly_entries_exits`: latest MRT annual entries plus exits, divided by 12.
- `target_population`: residents aged 20-44 in the configured station district.
- `competitor_count`: active restaurant business registrations in the configured station district.
- `real_estate_cost_index`: district-level cost proxy.
- `transport_access_index`: station entrance count normalized within demo stations.

Current score output:

```text
data/processed/station_scores.csv
```

At the time of the current processed run, the top-ranked trade area is `劍潭`, mainly because it combines a large target population, lower restaurant competition, and a relatively affordable cost proxy.

## Dashboard

The Streamlit dashboard reads `data/processed/station_scores.csv` when available. If the processed score file does not exist, it falls back to bundled sample data.

Dashboard features:

- Top-station KPI cards.
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
  features.py                Feature engineering helpers.
  scoring.py                 Core location scoring logic.
scripts/
  download_public_data.py    Downloads core public datasets.
  build_competitor_summary.py Streams restaurant registrations into competitor counts.
  build_station_features.py  Builds the station-level feature table.
  run_scoring.py             Builds ranked station scores from a feature CSV.
app/
  streamlit_app.py           Streamlit dashboard entry point.
data/
  raw/                       Local raw data outputs; large CSVs are ignored by git.
  processed/                 Reproducible processed feature and score outputs.
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
  test_features.py
  test_run_scoring_script.py
  test_scoring.py
```

## Product Planning Materials

Use these files when writing a product brief, technical note, or external project overview:

- Architecture: `docs/architecture.md`
- Data sources: `docs/data_sources.md`
- Demand evidence: `docs/demand_evidence.md`
- Report outline: `docs/report_outline.md`
- Implementation plan and checklist: `docs/superpowers/plans/2026-06-04-retail-location-scout.md`

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
- The model ranks relative attractiveness among configured demo stations; it does not predict revenue.
- Future versions should add finer-grained POI/geocoding, rental data, user feedback, and validation against actual store outcomes.

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

The script streams the source CSV and writes only a small summary file.

If public-data endpoints change, update `retail_scout/data_catalog.py` and rerun the relevant download script.
