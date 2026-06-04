from __future__ import annotations

from pathlib import Path

import pandas as pd


DISPLAY_COLUMNS = [
    "station_name",
    "economic_opportunity_index",
    "feasibility_ratio",
    "break_even_capture_rate",
    "accessible_demand",
    "competition_adjusted_customers",
    "estimated_monthly_revenue",
    "estimated_gross_profit",
    "operating_cost_proxy",
    "monthly_entries_exits",
    "target_population",
    "competitor_count",
    "real_estate_cost_index",
    "transport_access_index",
    "recommendation_reason",
]


def load_ranked_locations(scored_path: Path, sample_path: Path) -> pd.DataFrame:
    path = scored_path if scored_path.exists() else sample_path
    df = pd.read_csv(path)
    if "location_score" in df.columns:
        return df.sort_values("location_score", ascending=False).reset_index(drop=True)
    return df


def build_summary(df: pd.DataFrame) -> dict[str, object]:
    ranked = df.sort_values("location_score", ascending=False).reset_index(drop=True)
    top = ranked.iloc[0]
    lowest_competition = df.sort_values("competitor_count", ascending=True).iloc[0]

    summary = {
        "top_station": top["station_name"],
        "top_score": float(top["location_score"]),
        "average_monthly_entries_exits": float(df["monthly_entries_exits"].mean()),
        "lowest_competition_station": lowest_competition["station_name"],
        "lowest_competition_count": float(lowest_competition["competitor_count"]),
    }
    if "feasibility_ratio" in df.columns:
        summary["top_feasibility_ratio"] = float(top["feasibility_ratio"])
    return summary


def filter_ranked_locations(df: pd.DataFrame, minimum_score: float) -> pd.DataFrame:
    filtered = df[df["location_score"] >= minimum_score]
    return filtered.sort_values("location_score", ascending=False).reset_index(drop=True)


def display_table(df: pd.DataFrame) -> pd.DataFrame:
    available_columns = [column for column in DISPLAY_COLUMNS if column in df.columns]
    return df.loc[:, available_columns].copy()
