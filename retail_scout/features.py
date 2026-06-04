from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class StationConfig:
    station_name: str
    district: str
    mrt_station_names: tuple[str, ...]
    entrance_match_texts: tuple[str, ...]
    real_estate_cost_index: float


DEMO_STATIONS = [
    StationConfig(
        station_name="台北車站",
        district="臺北市中正區",
        mrt_station_names=("台北車站BL", "台北車站R"),
        entrance_match_texts=("台北車站",),
        real_estate_cost_index=95.0,
    ),
    StationConfig(
        station_name="中山",
        district="臺北市中山區",
        mrt_station_names=("中山R", "中山G"),
        entrance_match_texts=("中山站",),
        real_estate_cost_index=88.0,
    ),
    StationConfig(
        station_name="公館",
        district="臺北市中正區",
        mrt_station_names=("公館",),
        entrance_match_texts=("公館站",),
        real_estate_cost_index=76.0,
    ),
    StationConfig(
        station_name="古亭",
        district="臺北市中正區",
        mrt_station_names=("古亭",),
        entrance_match_texts=("古亭站",),
        real_estate_cost_index=68.0,
    ),
    StationConfig(
        station_name="科技大樓",
        district="臺北市大安區",
        mrt_station_names=("科技大樓",),
        entrance_match_texts=("科技大樓站",),
        real_estate_cost_index=63.0,
    ),
    StationConfig(
        station_name="劍潭",
        district="臺北市士林區",
        mrt_station_names=("劍潭",),
        entrance_match_texts=("劍潭站",),
        real_estate_cost_index=58.0,
    ),
]


def parse_roc_year(value: str) -> int:
    match = re.search(r"\d+", value)
    if not match:
        raise ValueError(f"Cannot parse ROC year from {value!r}")
    return int(match.group())


def extract_target_population_by_district(
    rows: Iterable[dict[str, str]],
    start_age: int = 20,
    end_age: int = 44,
) -> dict[str, int]:
    population: dict[str, int] = {}
    for row in rows:
        district = row["區域別"]
        population.setdefault(district, 0)
        for age in range(start_age, end_age + 1):
            population[district] += _to_int(row.get(f"{age}歲-男", "0"))
            population[district] += _to_int(row.get(f"{age}歲-女", "0"))
    return population


def count_active_restaurants_by_district(
    rows: Iterable[dict[str, str]],
    districts: Iterable[str],
) -> dict[str, int]:
    counts = {district: 0 for district in districts}
    normalized_districts = {
        _normalize_taipei_name(district): district for district in districts
    }

    for row in rows:
        status = row.get("登記狀態", "")
        if _is_inactive_status(status):
            continue

        address = _normalize_taipei_name(row.get("商業地址", ""))
        for normalized_district, district in normalized_districts.items():
            if normalized_district in address:
                counts[district] += 1
                break

    return counts


def build_station_feature_rows(
    *,
    stations: list[StationConfig],
    mrt_rows: list[dict[str, str]],
    entrance_rows: list[dict[str, str]],
    population_by_district: dict[str, int],
    competitor_counts: dict[str, int],
) -> list[dict[str, object]]:
    latest_year = max(parse_roc_year(row["統計期"]) for row in mrt_rows)
    entrance_counts = {
        station.station_name: _count_station_entrances(station, entrance_rows)
        for station in stations
    }
    max_entrance_count = max(entrance_counts.values()) if entrance_counts else 1
    if max_entrance_count == 0:
        max_entrance_count = 1

    feature_rows: list[dict[str, object]] = []
    for station in stations:
        annual_entries_exits = _sum_latest_mrt_entries_exits(
            station=station,
            mrt_rows=mrt_rows,
            latest_year=latest_year,
        )
        feature_rows.append(
            {
                "station_name": station.station_name,
                "monthly_entries_exits": round(annual_entries_exits / 12.0, 2),
                "target_population": population_by_district.get(station.district, 0),
                "competitor_count": competitor_counts.get(station.district, 0),
                "real_estate_cost_index": station.real_estate_cost_index,
                "transport_access_index": round(
                    entrance_counts[station.station_name] / max_entrance_count,
                    2,
                ),
            }
        )

    return feature_rows


def _sum_latest_mrt_entries_exits(
    *,
    station: StationConfig,
    mrt_rows: Iterable[dict[str, str]],
    latest_year: int,
) -> int:
    station_names = set(station.mrt_station_names)
    total = 0
    for row in mrt_rows:
        if parse_roc_year(row["統計期"]) != latest_year:
            continue
        if row["捷運站別"] not in station_names:
            continue
        total += _to_int(row["進站人次"]) + _to_int(row["出站人次"])
    return total


def _count_station_entrances(
    station: StationConfig,
    entrance_rows: Iterable[dict[str, str]],
) -> int:
    return sum(
        1
        for row in entrance_rows
        if any(text in row["出入口名稱"] for text in station.entrance_match_texts)
    )


def _is_inactive_status(status: str) -> bool:
    inactive_terms = ("歇業", "撤銷", "廢止", "停業")
    return any(term in status for term in inactive_terms)


def _normalize_taipei_name(value: str) -> str:
    return value.replace("台", "臺")


def _to_int(value: str) -> int:
    text = value.replace(",", "").strip()
    if not text:
        return 0
    return int(float(text))
