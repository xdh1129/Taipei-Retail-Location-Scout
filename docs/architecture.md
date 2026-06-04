# Architecture

## Current Architecture

```mermaid
flowchart LR
    A["Open data pages and CSV/SHP files"] --> B["Ingestion scripts"]
    B --> C["Raw files in data/raw"]
    C --> D["Cleaning and feature builder"]
    D --> E["Station feature table"]
    E --> F["Scoring module"]
    F --> G["Processed station scores"]
    G --> H["Streamlit dashboard"]
    G --> I["CSV export"]
```

## Production-Scale Architecture

```mermaid
flowchart LR
    A["Government open data, OSM, optional geocoding"] --> B["Scheduled ingestion"]
    B --> C["Object storage data lake"]
    C --> D["Batch processing with Spark or DuckDB"]
    D --> E["Feature store"]
    E --> F["Scoring service"]
    F --> G["Dashboard and API"]
    F --> H["Brief export"]
```

## Data Flow

1. Download public datasets into `data/raw`.
2. Normalize field names and filter the initial scope to Taipei MRT-adjacent retail trade areas.
3. Aggregate every source to a station-level feature table.
4. Score each station with a transparent weighted formula.
5. Serve the ranked result through Streamlit and export the table for downstream analysis.

## Current Boundary

The current version uses station trade areas instead of exact store parcels. This keeps the system practical while still demonstrating data monetization: the customer pays for faster first-pass site screening before spending money on lease visits or consultants.
