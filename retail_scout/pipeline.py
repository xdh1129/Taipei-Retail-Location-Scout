from __future__ import annotations

import re
from pathlib import Path

import duckdb

# Taipei Metro line codes that appear as a suffix on station rows in the
# entries/exits dataset (e.g. 中山R, 中山G, 台北車站BL).
_LINE_SUFFIX_RE = re.compile(r"(BL|BR|[RGOY])$")


def normalize_taipei_name(value: str) -> str:
    return value.replace("台", "臺")


def normalize_station_name(raw: str) -> str:
    name = raw.strip()
    stripped = _LINE_SUFFIX_RE.sub("", name)
    return stripped if stripped else name


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


def stage_entrances(con: duckdb.DuckDBPyConnection, src_table: str = "raw_entrances") -> None:
    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_entrances AS
        SELECT
            normalize_station_name(
                regexp_replace(出入口名稱, '(站?(出入口|出口)|M[0-9]).*$', '')
            ) AS station_name,
            CAST(經度 AS DOUBLE) AS lon,
            CAST(緯度 AS DOUBLE) AS lat
        FROM {src_table}
        WHERE 經度 IS NOT NULL AND 緯度 IS NOT NULL
        """
    )


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


def stage_population(con: duckdb.DuckDBPyConnection, src_table: str = "raw_population",
                     start_age: int = 20, end_age: int = 44) -> None:
    # Get the list of columns in the source table
    columns = [col[0] for col in con.execute(f"DESCRIBE {src_table}").fetchall()]

    # Build age terms only for columns that exist
    age_terms_list = []
    for age in range(start_age, end_age + 1):
        male_col = f"{age}歲-男"
        female_col = f"{age}歲-女"
        if male_col in columns:
            age_terms_list.append(f'COALESCE(CAST("{male_col}" AS BIGINT), 0)')
        if female_col in columns:
            age_terms_list.append(f'COALESCE(CAST("{female_col}" AS BIGINT), 0)')

    age_terms = " + ".join(age_terms_list) if age_terms_list else "0"

    con.execute(
        f"""
        CREATE OR REPLACE TABLE stg_population AS
        SELECT
            normalize_taipei_name(區域別) AS district,
            CAST(sum({age_terms}) AS BIGINT) AS target_population
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
