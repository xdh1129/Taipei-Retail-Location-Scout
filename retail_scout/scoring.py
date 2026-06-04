from __future__ import annotations

from typing import Iterable


DEFAULT_WEIGHTS = {
    "traffic": 0.30,
    "target_population": 0.25,
    "competition_gap": 0.20,
    "cost_affordability": 0.15,
    "transport_access": 0.10,
}


def normalize_values(values: Iterable[float]) -> list[float]:
    numeric_values = [float(value) for value in values]
    if not numeric_values:
        return []

    minimum = min(numeric_values)
    maximum = max(numeric_values)
    if maximum == minimum:
        return [0.0 for _ in numeric_values]

    return [(value - minimum) / (maximum - minimum) for value in numeric_values]


def compute_location_scores(rows: list[dict[str, object]]) -> list[dict[str, object]]:
    if not rows:
        return []

    traffic = normalize_values(row["monthly_entries_exits"] for row in rows)
    population = normalize_values(row["target_population"] for row in rows)
    competition_gap = normalize_values(
        float(row["target_population"]) / (float(row["competitor_count"]) + 1.0)
        for row in rows
    )
    cost_pressure = normalize_values(row["real_estate_cost_index"] for row in rows)
    cost_affordability = [1.0 - value for value in cost_pressure]
    access = normalize_values(row["transport_access_index"] for row in rows)

    scored_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        score = (
            DEFAULT_WEIGHTS["traffic"] * traffic[index]
            + DEFAULT_WEIGHTS["target_population"] * population[index]
            + DEFAULT_WEIGHTS["competition_gap"] * competition_gap[index]
            + DEFAULT_WEIGHTS["cost_affordability"] * cost_affordability[index]
            + DEFAULT_WEIGHTS["transport_access"] * access[index]
        )

        enriched = dict(row)
        enriched["location_score"] = round(score * 100, 2)
        enriched["recommendation_reason"] = build_recommendation_reason(
            traffic=traffic[index],
            population=population[index],
            competition_gap=competition_gap[index],
            cost_affordability=cost_affordability[index],
        )
        scored_rows.append(enriched)

    return sorted(scored_rows, key=lambda item: item["location_score"], reverse=True)


def build_recommendation_reason(
    *,
    traffic: float,
    population: float,
    competition_gap: float,
    cost_affordability: float,
) -> str:
    reasons: list[str] = []

    if competition_gap >= 0.70:
        reasons.append("strong demand-to-competition gap")
    if traffic >= 0.70:
        reasons.append("high transit footfall")
    if population >= 0.70:
        reasons.append("large target customer base")
    if cost_affordability >= 0.70:
        reasons.append("relatively affordable cost proxy")

    if not reasons:
        return "balanced but not dominant across current indicators"

    return "; ".join(reasons)
