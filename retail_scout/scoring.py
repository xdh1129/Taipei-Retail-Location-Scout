from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class EconomicAssumptions:
    """Transparent assumptions for the retail economic-opportunity proxy."""

    traffic_capture_rate: float = 0.00065
    local_monthly_visit_rate: float = 0.28
    access_base_multiplier: float = 0.85
    access_lift_multiplier: float = 0.30
    competitor_scale: float = 300.0
    competition_elasticity: float = 1.15
    average_ticket_size: float = 160.0
    gross_margin: float = 0.62
    base_monthly_operating_cost: float = 360_000.0
    rent_index_cost_multiplier: float = 4_500.0


DEFAULT_ASSUMPTIONS = EconomicAssumptions()


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

    estimates = [estimate_profit_opportunity(row) for row in rows]

    scored_rows: list[dict[str, object]] = []
    for index, row in enumerate(rows):
        enriched = dict(row)
        enriched.update(estimates[index])
        enriched["location_score"] = estimates[index]["economic_opportunity_index"]
        enriched["recommendation_reason"] = build_recommendation_reason(
            accessible_demand=estimates[index]["accessible_demand"],
            competition_adjusted_customers=estimates[index][
                "competition_adjusted_customers"
            ],
            feasibility_ratio=estimates[index]["feasibility_ratio"],
            break_even_capture_rate=estimates[index]["break_even_capture_rate"],
        )
        scored_rows.append(enriched)

    return sorted(
        scored_rows,
        key=lambda item: (item["location_score"], item["feasibility_ratio"]),
        reverse=True,
    )


def estimate_profit_opportunity(
    row: dict[str, object],
    assumptions: EconomicAssumptions = DEFAULT_ASSUMPTIONS,
) -> dict[str, float]:
    monthly_entries_exits = float(row["monthly_entries_exits"])
    target_population = float(row["target_population"])
    competitor_count = float(row["competitor_count"])
    cost_index = float(row["real_estate_cost_index"])
    access_index = float(row["transport_access_index"])

    transit_demand = monthly_entries_exits * assumptions.traffic_capture_rate
    local_demand = target_population * assumptions.local_monthly_visit_rate
    access_multiplier = (
        assumptions.access_base_multiplier
        + assumptions.access_lift_multiplier * access_index
    )
    accessible_demand = (transit_demand + local_demand) * access_multiplier

    competition_pressure = (
        1.0 + competitor_count / assumptions.competitor_scale
    ) ** assumptions.competition_elasticity
    competition_adjusted_customers = accessible_demand / competition_pressure

    estimated_monthly_revenue = (
        competition_adjusted_customers * assumptions.average_ticket_size
    )
    estimated_gross_profit = estimated_monthly_revenue * assumptions.gross_margin
    operating_cost_proxy = (
        assumptions.base_monthly_operating_cost
        + cost_index * assumptions.rent_index_cost_multiplier
    )
    feasibility_ratio = estimated_gross_profit / max(operating_cost_proxy, 1.0)
    economic_opportunity_index = min(feasibility_ratio, 1.0) * 100.0
    profit_gap_proxy = estimated_gross_profit - operating_cost_proxy
    required_customers = operating_cost_proxy / (
        assumptions.average_ticket_size * assumptions.gross_margin
    )
    break_even_capture_rate = required_customers / max(accessible_demand, 1.0)

    return {
        "accessible_demand": round(accessible_demand, 2),
        "competition_adjusted_customers": round(competition_adjusted_customers, 2),
        "estimated_monthly_revenue": round(estimated_monthly_revenue, 2),
        "estimated_gross_profit": round(estimated_gross_profit, 2),
        "operating_cost_proxy": round(operating_cost_proxy, 2),
        "feasibility_ratio": round(feasibility_ratio, 4),
        "economic_opportunity_index": round(economic_opportunity_index, 2),
        "profit_gap_proxy": round(profit_gap_proxy, 2),
        "break_even_capture_rate": round(break_even_capture_rate, 4),
    }


def build_recommendation_reason(
    *,
    accessible_demand: float,
    competition_adjusted_customers: float,
    feasibility_ratio: float,
    break_even_capture_rate: float,
) -> str:
    reasons: list[str] = []
    competition_retention = competition_adjusted_customers / max(accessible_demand, 1.0)

    if feasibility_ratio >= 1.0:
        reasons.append("clears cost proxy under current assumptions")
    elif feasibility_ratio >= 0.85:
        reasons.append("near break-even under conservative assumptions")
    elif feasibility_ratio >= 0.65:
        reasons.append("moderate feasibility with execution sensitivity")
    if break_even_capture_rate <= 0.35:
        reasons.append("low break-even capture requirement")
    if competition_retention >= 0.55:
        reasons.append("strong demand-to-competition gap")
    if accessible_demand >= 15_000:
        reasons.append("large accessible demand base")

    if not reasons:
        return "needs stronger capture, ticket size, or rent assumptions"

    return "; ".join(reasons)
