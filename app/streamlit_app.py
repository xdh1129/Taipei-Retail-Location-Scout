from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd
import streamlit as st


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from retail_scout.dashboard import (
    build_summary,
    display_table,
    filter_ranked_locations,
    load_ranked_locations,
)


SCORED_PATH = ROOT / "data" / "processed" / "station_scores.csv"
SAMPLE_PATH = ROOT / "data" / "sample" / "station_features.csv"
FEATURE_PATH = ROOT / "data" / "processed" / "station_features.csv"
METADATA_PATH = ROOT / "data" / "processed" / "station_features_metadata.json"


st.set_page_config(page_title="Taipei Retail Location Scout", layout="wide")


@st.cache_data
def load_table(scored_path: str, sample_path: str) -> pd.DataFrame:
    return load_ranked_locations(Path(scored_path), Path(sample_path))


df = load_table(str(SCORED_PATH), str(SAMPLE_PATH))

st.title("Taipei Retail Location Scout")
st.caption("Retail site scoring for Taipei MRT-adjacent coffee, beverage, and light-meal trade areas.")

if "location_score" not in df.columns:
    st.warning("Run `python3 scripts/run_scoring.py` to generate ranked location scores.")
else:
    summary = build_summary(df)

    metric_1, metric_2, metric_3, metric_4 = st.columns(4)
    metric_1.metric("Top Station", summary["top_station"], f'{summary["top_score"]:.2f}')
    metric_2.metric(
        "Avg Monthly Footfall",
        f'{summary["average_monthly_entries_exits"]:,.0f}',
    )
    metric_3.metric(
        "Lowest Competition",
        summary["lowest_competition_station"],
        f'{summary["lowest_competition_count"]:,.0f} businesses',
    )
    if "top_feasibility_ratio" in summary:
        metric_4.metric(
            "Top Feasibility",
            f'{summary["top_feasibility_ratio"]:.2f}x',
        )
    else:
        metric_4.metric("Trade Areas", f"{len(df)}")

    controls_left, controls_right = st.columns([1, 2])
    with controls_left:
        minimum_score = st.slider(
            "Minimum Score",
            min_value=0,
            max_value=100,
            value=0,
            step=5,
        )
    with controls_right:
        selected_station = st.selectbox(
            "Selected Trade Area",
            options=df["station_name"].tolist(),
        )

    filtered = filter_ranked_locations(df, minimum_score=float(minimum_score))
    table_tab, chart_tab, detail_tab = st.tabs(["Ranking", "Indicators", "Selected Area"])

    with table_tab:
        st.dataframe(
            display_table(filtered),
            use_container_width=True,
            hide_index=True,
            column_config={
                "station_name": st.column_config.TextColumn("Station"),
                "economic_opportunity_index": st.column_config.ProgressColumn(
                    "Economic Opportunity",
                    format="%.2f",
                    min_value=0,
                    max_value=100,
                ),
                "feasibility_ratio": st.column_config.NumberColumn(
                    "Feasibility Ratio",
                    format="%.2f",
                ),
                "break_even_capture_rate": st.column_config.NumberColumn(
                    "Break-even Capture",
                    format="%.2f",
                ),
                "accessible_demand": st.column_config.NumberColumn(
                    "Accessible Demand",
                    format="%,.0f",
                ),
                "competition_adjusted_customers": st.column_config.NumberColumn(
                    "Adjusted Customers",
                    format="%,.0f",
                ),
                "estimated_monthly_revenue": st.column_config.NumberColumn(
                    "Revenue Proxy",
                    format="%,.0f",
                ),
                "estimated_gross_profit": st.column_config.NumberColumn(
                    "Gross Profit Proxy",
                    format="%,.0f",
                ),
                "operating_cost_proxy": st.column_config.NumberColumn(
                    "Cost Proxy",
                    format="%,.0f",
                ),
                "monthly_entries_exits": st.column_config.NumberColumn(
                    "Monthly Footfall",
                    format="%,.0f",
                ),
                "target_population": st.column_config.NumberColumn(
                    "Target Population",
                    format="%,.0f",
                ),
                "competitor_count": st.column_config.NumberColumn(
                    "Competitors",
                    format="%,.0f",
                ),
                "real_estate_cost_index": st.column_config.NumberColumn(
                    "Cost Index",
                    format="%.1f",
                ),
                "transport_access_index": st.column_config.NumberColumn(
                    "Access Index",
                    format="%.2f",
                ),
                "recommendation_reason": st.column_config.TextColumn("Signal"),
            },
        )
        st.download_button(
            "Download CSV",
            data=filtered.to_csv(index=False).encode("utf-8"),
            file_name="retail_location_scores.csv",
            mime="text/csv",
        )

    with chart_tab:
        chart_data = filtered.set_index("station_name")[
            [
                "location_score",
                "feasibility_ratio",
                "target_population",
                "competitor_count",
                "transport_access_index",
            ]
        ].copy()
        chart_data["feasibility_ratio"] = chart_data["feasibility_ratio"] * 100
        chart_data["target_population"] = chart_data["target_population"] / chart_data[
            "target_population"
        ].max() * 100
        chart_data["competitor_count"] = 100 - (
            chart_data["competitor_count"] / chart_data["competitor_count"].max() * 100
        )
        chart_data["transport_access_index"] = chart_data["transport_access_index"] * 100
        chart_data = chart_data.rename(
            columns={
                "location_score": "Score",
                "feasibility_ratio": "Feasibility",
                "target_population": "Target Population",
                "competitor_count": "Competition Gap",
                "transport_access_index": "Access",
            }
        )
        st.bar_chart(chart_data)

    with detail_tab:
        selected = df[df["station_name"] == selected_station].iloc[0]
        detail_left, detail_right = st.columns([1, 1])
        with detail_left:
            st.subheader(selected["station_name"])
            st.metric("Economic Opportunity", f'{selected["location_score"]:.2f}')
            if "feasibility_ratio" in selected.index:
                st.metric(
                    "Feasibility Ratio",
                    f'{selected["feasibility_ratio"]:.2f}x',
                )
            if "break_even_capture_rate" in selected.index:
                st.metric(
                    "Break-even Capture Rate",
                    f'{selected["break_even_capture_rate"] * 100:.1f}%',
                )
            st.write(selected["recommendation_reason"])
        with detail_right:
            detail_values = [
                {"Indicator": "Monthly Footfall", "Value": selected["monthly_entries_exits"]},
                {"Indicator": "Target Population", "Value": selected["target_population"]},
                {"Indicator": "Competitors", "Value": selected["competitor_count"]},
                {"Indicator": "Cost Index", "Value": selected["real_estate_cost_index"]},
                {"Indicator": "Access Index", "Value": selected["transport_access_index"]},
            ]
            if "accessible_demand" in selected.index:
                detail_values.extend(
                    [
                        {
                            "Indicator": "Accessible Demand",
                            "Value": selected["accessible_demand"],
                        },
                        {
                            "Indicator": "Competition-Adjusted Customers",
                            "Value": selected["competition_adjusted_customers"],
                        },
                        {
                            "Indicator": "Estimated Monthly Revenue",
                            "Value": selected["estimated_monthly_revenue"],
                        },
                        {
                            "Indicator": "Operating Cost Proxy",
                            "Value": selected["operating_cost_proxy"],
                        },
                        {
                            "Indicator": "Gap Diagnostic",
                            "Value": selected["profit_gap_proxy"],
                        },
                    ]
                )
            detail_rows = pd.DataFrame(detail_values)
            st.dataframe(detail_rows, use_container_width=True, hide_index=True)

    source_line = "Processed data"
    if FEATURE_PATH.exists():
        source_line += f" from `{FEATURE_PATH.relative_to(ROOT)}`"
    if METADATA_PATH.exists():
        source_line += f" with metadata in `{METADATA_PATH.relative_to(ROOT)}`"
    st.caption(source_line)
