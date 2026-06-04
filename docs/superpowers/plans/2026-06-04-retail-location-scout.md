# Retail Location Scout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build an explainable location-intelligence prototype that ranks Taipei MRT-adjacent retail trade areas for coffee, beverage, and light-meal expansion decisions.

**Architecture:** Public datasets are downloaded into `data/raw`, cleaned into a station-level feature table, scored with a transparent weighted formula, and delivered through a Streamlit dashboard. The product brief explains how this system can scale into scheduled ingestion, data lake storage, batch processing, a feature store, and a dashboard/API product.

**Tech Stack:** Python, csv/pandas, DuckDB optional, Streamlit, pydeck optional, government open data, OpenStreetMap optional.

---

## Day 1: Scope and Skeleton

- [ ] Confirm the initial scope: Taipei MRT stations, coffee/beverage/light-meal customer segment, station-level scoring.
- [ ] Keep `README.md`, `docs/architecture.md`, `docs/data_sources.md`, and `docs/report_outline.md` aligned with the external product narrative.
- [ ] Verify the smoke test:

```bash
python3 -m unittest tests/test_scoring.py
```

Expected result: 3 tests pass.

## Phase 2: Core Public Data Collection

- [x] Download Taipei MRT station entry/exit totals from https://data.gov.tw/dataset/133184 into `data/raw/mrt_station_entries.csv`.
- [x] Download Taipei MRT entrance coordinates from https://data.gov.tw/en/datasets/128428 into `data/raw/mrt_entrances.csv`.
- [x] Download population data from https://data.gov.tw/dataset/77132 into `data/raw/population_by_village.csv`.
- [x] Record the exact resource URLs, access dates, and license notes in `docs/data_sources.md`.

Core public data output files:

```text
data/raw/mrt_station_entries.csv
data/raw/mrt_entrances.csv
data/raw/population_by_village.csv
data/raw/public_data_manifest.json
```

## Phase 3: Feature Table

- [x] Create a station-level table with these columns:

```text
station_name,monthly_entries_exits,target_population,competitor_count,real_estate_cost_index,transport_access_index
```

- [x] Use MRT station totals for `monthly_entries_exits`.
- [x] Use district-level or manually joined village-level population for `target_population`.
- [x] Use OpenStreetMap POI counts or restaurant registration counts for `competitor_count`.
- [x] Use real-price registration or a documented district-level proxy for `real_estate_cost_index`.
- [x] Save the feature table as `data/sample/station_features.csv` for the demo and `data/processed/station_features.csv` for real processed data.

Feature table output files:

```text
data/processed/competitor_counts_by_district.csv
data/processed/competitor_summary_manifest.json
data/processed/station_features.csv
data/processed/station_features_metadata.json
data/processed/station_scores.csv
```

## Day 4: Scoring and Dashboard

- [x] Run the scoring script:

```bash
python3 scripts/run_scoring.py
```

Expected result: `data/processed/station_scores.csv` is created.

- [x] Run the Streamlit app:

```bash
streamlit run app/streamlit_app.py
```

Expected result: a ranked table appears with a top station metric.

Day 4 dashboard features:

```text
Top-station KPI cards
Minimum-score filter
Ranked trade-area table
Indicator chart
Selected-area detail view
CSV download button
```

## Day 5: Demand Evidence

- [x] Capture evidence that location intelligence products exist and charge through subscriptions or paid reports.
- [x] Quantify time saved: compare manual station-by-station research with the dashboard workflow.
- [x] Estimate willingness to pay: use NT$990/report and NT$2,990/month as initial prices for small operators.
- [x] Add charts or tables to the product brief showing active food-service competition and station ranking.

Day 5 output file:

```text
docs/demand_evidence.md
```

## Day 6: Product Brief and Repository Polish

- [ ] Write the English product brief using `docs/report_outline.md`.
- [ ] Add the GitHub URL on the first page.
- [ ] Include the architecture diagram from `docs/architecture.md`.
- [ ] Include a limitations paragraph: no revenue prediction, rent is proxied, geocoding may be incomplete.

## Day 7: Deployment and Release Check

- [ ] Deploy the Streamlit app if time allows.
- [ ] Confirm the README quick-start commands work.
- [ ] Export the product brief PDF.
- [ ] Share the product brief and repository URL.
