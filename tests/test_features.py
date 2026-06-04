import unittest

from retail_scout.features import (
    StationConfig,
    build_station_feature_rows,
    count_active_restaurants_by_district,
    extract_target_population_by_district,
    parse_roc_year,
)


class FeatureBuilderTests(unittest.TestCase):
    def test_parse_roc_year_extracts_numeric_year(self):
        self.assertEqual(parse_roc_year("114年"), 114)

    def test_extract_target_population_by_district_sums_ages_20_to_44(self):
        row = {
            "區域別": "臺北市大安區",
            "20歲-男": "10",
            "20歲-女": "12",
            "44歲-男": "7",
            "44歲-女": "9",
        }
        for age in range(21, 44):
            row[f"{age}歲-男"] = "1"
            row[f"{age}歲-女"] = "2"

        result = extract_target_population_by_district([row])

        self.assertEqual(result["臺北市大安區"], 107)

    def test_count_active_restaurants_by_district_uses_address_and_status(self):
        restaurants = [
            {"商業地址": "臺北市大安區復興南路一段1號", "登記狀態": "核准設立"},
            {"商業地址": "臺北市大安區忠孝東路一段2號", "登記狀態": "歇業／撤銷"},
            {"商業地址": "臺北市中正區羅斯福路三段3號", "登記狀態": "核准設立"},
        ]

        counts = count_active_restaurants_by_district(
            restaurants,
            districts=["臺北市大安區", "臺北市中正區"],
        )

        self.assertEqual(counts["臺北市大安區"], 1)
        self.assertEqual(counts["臺北市中正區"], 1)

    def test_build_station_feature_rows_combines_raw_sources(self):
        station = StationConfig(
            station_name="台北車站",
            district="臺北市中正區",
            mrt_station_names=("台北車站BL", "台北車站R"),
            entrance_match_texts=("台北車站",),
            real_estate_cost_index=95.0,
        )
        mrt_rows = [
            {"統計期": "113年", "捷運站別": "台北車站BL", "進站人次": "10", "出站人次": "20"},
            {"統計期": "114年", "捷運站別": "台北車站BL", "進站人次": "120", "出站人次": "240"},
            {"統計期": "114年", "捷運站別": "台北車站R", "進站人次": "60", "出站人次": "180"},
        ]
        entrances = [
            {"出入口名稱": "台北車站M1"},
            {"出入口名稱": "台北車站M2"},
        ]
        population_by_district = {"臺北市中正區": 5000}
        competitor_counts = {"臺北市中正區": 30}

        rows = build_station_feature_rows(
            stations=[station],
            mrt_rows=mrt_rows,
            entrance_rows=entrances,
            population_by_district=population_by_district,
            competitor_counts=competitor_counts,
        )

        self.assertEqual(
            rows,
            [
                {
                    "station_name": "台北車站",
                    "monthly_entries_exits": 50.0,
                    "target_population": 5000,
                    "competitor_count": 30,
                    "real_estate_cost_index": 95.0,
                    "transport_access_index": 1.0,
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
