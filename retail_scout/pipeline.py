from __future__ import annotations

import re

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
