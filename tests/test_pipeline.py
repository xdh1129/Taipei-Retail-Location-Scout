import unittest

import duckdb

from retail_scout.pipeline import connect, normalize_station_name, normalize_taipei_name, stage_stations, stage_entrances, stage_station_district, stage_competitors, stage_cost, stage_population, build_feature_mart


class StationNameTests(unittest.TestCase):
    def test_strips_single_line_suffix(self):
        self.assertEqual(normalize_station_name("中山R"), "中山")
        self.assertEqual(normalize_station_name("中山G"), "中山")

    def test_strips_multi_letter_line_suffix(self):
        self.assertEqual(normalize_station_name("台北車站BL"), "台北車站")
        self.assertEqual(normalize_station_name("台北車站R"), "台北車站")

    def test_leaves_plain_name_untouched(self):
        self.assertEqual(normalize_station_name("公館"), "公館")
        self.assertEqual(normalize_station_name("科技大樓"), "科技大樓")

    def test_does_not_blank_out_bare_latin_token(self):
        self.assertEqual(normalize_station_name("R"), "R")
        self.assertEqual(normalize_station_name("BR"), "BR")

    def test_normalize_taipei_name(self):
        self.assertEqual(normalize_taipei_name("台北市大安區"), "臺北市大安區")


class StageStationsTests(unittest.TestCase):
    def _seed_raw_mrt(self, con):
        con.execute(
            "CREATE TABLE raw_mrt (統計期 VARCHAR, 捷運站別 VARCHAR, 進站人次 BIGINT, 出站人次 BIGINT)"
        )
        con.executemany(
            "INSERT INTO raw_mrt VALUES (?, ?, ?, ?)",
            [
                ("113年", "中山R", 10, 20),
                ("114年", "中山R", 120, 240),
                ("114年", "中山G", 60, 180),
                ("114年", "一日票", 999, 999),
            ],
        )

    def test_stage_stations_merges_lines_and_keeps_latest_year(self):
        con = connect()
        self._seed_raw_mrt(con)

        stage_stations(con)
        rows = con.execute(
            "SELECT station_name, monthly_entries_exits FROM stg_stations ORDER BY station_name"
        ).fetchall()

        # 中山R(114) 120+240 + 中山G(114) 60+180 = 600; /12 = 50.0
        self.assertIn(("中山", 50.0), rows)
        # 一日票 normalizes to 一日票 (no line suffix) and is still present at this
        # stage; it is dropped later by the entrances join.
        self.assertTrue(any(name == "中山" for name, _ in rows))


class StageEntrancesTests(unittest.TestCase):
    def test_stage_entrances_extracts_station_and_coords(self):
        con = connect()
        con.execute("CREATE TABLE raw_entrances (出入口名稱 VARCHAR, 經度 DOUBLE, 緯度 DOUBLE)")
        con.executemany(
            "INSERT INTO raw_entrances VALUES (?, ?, ?)",
            [
                ("中山站出口1", 121.520, 25.052),
                ("中山站出口2", 121.521, 25.053),
                ("公館站出口1", 121.534, 25.014),
            ],
        )

        stage_entrances(con)
        rows = con.execute(
            "SELECT station_name, count(*) FROM stg_entrances GROUP BY station_name ORDER BY station_name"
        ).fetchall()

        self.assertEqual(rows, [("中山", 2), ("公館", 1)])

    def test_stage_entrances_handles_taipei_main_m_suffix(self):
        con = connect()
        con.execute("CREATE TABLE raw_entrances (出入口名稱 VARCHAR, 經度 DOUBLE, 緯度 DOUBLE)")
        con.executemany(
            "INSERT INTO raw_entrances VALUES (?, ?, ?)",
            [("台北車站M1", 121.517, 25.046), ("台北車站M8", 121.517, 25.047)],
        )
        stage_entrances(con)
        rows = con.execute(
            "SELECT station_name, count(*) FROM stg_entrances GROUP BY station_name"
        ).fetchall()
        self.assertEqual(rows, [("台北車站", 2)])


class StationDistrictTests(unittest.TestCase):
    def _seed(self, con):
        # Two unit-square districts side by side: A = x in [0,1], B = x in [1,2].
        con.execute("CREATE TABLE stg_districts (district VARCHAR, geom GEOMETRY)")
        con.execute(
            "INSERT INTO stg_districts VALUES "
            "('臺北市A區', ST_GeomFromText('POLYGON((0 0,1 0,1 1,0 1,0 0))')), "
            "('臺北市B區', ST_GeomFromText('POLYGON((1 0,2 0,2 1,1 1,1 0))'))"
        )
        con.execute("CREATE TABLE stg_entrances (station_name VARCHAR, lon DOUBLE, lat DOUBLE)")
        con.executemany(
            "INSERT INTO stg_entrances VALUES (?, ?, ?)",
            [
                ("StationInA", 0.5, 0.5),
                ("StationInA", 0.6, 0.4),   # both in A
                ("Border", 0.5, 0.5),       # one in A
                ("Border", 0.5, 0.5),       # one in A -> modal A
                ("Border", 1.5, 0.5),       # one in B
                ("Outside", 9.0, 9.0),      # in neither -> dropped
            ],
        )

    def test_station_district_uses_modal_and_drops_outside(self):
        con = connect()
        self._seed(con)

        stage_station_district(con)
        rows = dict(
            con.execute("SELECT station_name, district FROM stg_station_district").fetchall()
        )

        self.assertEqual(rows["StationInA"], "臺北市A區")
        self.assertEqual(rows["Border"], "臺北市A區")
        self.assertNotIn("Outside", rows)


class StageCompetitorsTests(unittest.TestCase):
    def test_counts_active_restaurants_per_district(self):
        con = connect()
        con.execute("CREATE TABLE raw_registry (商業地址 VARCHAR, 登記狀態 VARCHAR)")
        con.executemany(
            "INSERT INTO raw_registry VALUES (?, ?)",
            [
                ("臺北市大安區復興南路一段1號", "核准設立"),
                ("台北市大安區忠孝東路一段2號", "核准設立"),  # 台 -> 臺
                ("臺北市大安區仁愛路3號", "歇業／撤銷"),       # inactive
                ("臺北市中正區羅斯福路三段3號", "核准設立"),
                ("新北市板橋區中山路1號", "核准設立"),          # not Taipei
            ],
        )

        stage_competitors(con)
        rows = dict(
            con.execute("SELECT district, competitor_count FROM stg_competitors").fetchall()
        )

        self.assertEqual(rows["臺北市大安區"], 2)
        self.assertEqual(rows["臺北市中正區"], 1)
        self.assertNotIn("新北市板橋區", rows)


class StagePopulationCostTests(unittest.TestCase):
    def test_population_sums_target_ages_for_taipei(self):
        con = connect()
        con.execute(
            'CREATE TABLE raw_population (區域別 VARCHAR, "20歲-男" BIGINT, "20歲-女" BIGINT, "44歲-男" BIGINT, "44歲-女" BIGINT)'
        )
        con.executemany(
            "INSERT INTO raw_population VALUES (?, ?, ?, ?, ?)",
            [
                ("臺北市大安區", 10, 12, 7, 9),
                ("台北市中正區", 1, 1, 1, 1),     # 台 -> 臺
                ("新北市板橋區", 100, 100, 100, 100),  # excluded
            ],
        )

        stage_population(con, start_age=20, end_age=44)
        rows = dict(
            con.execute("SELECT district, target_population FROM stg_population").fetchall()
        )

        self.assertEqual(rows["臺北市大安區"], 38)
        self.assertEqual(rows["臺北市中正區"], 4)
        self.assertNotIn("新北市板橋區", rows)

    def test_population_with_no_matching_age_columns_returns_zero(self):
        con = connect()
        con.execute("CREATE TABLE raw_population (區域別 VARCHAR)")
        con.execute("INSERT INTO raw_population VALUES ('臺北市大安區')")
        stage_population(con, start_age=20, end_age=44)
        rows = dict(con.execute("SELECT district, target_population FROM stg_population").fetchall())
        self.assertEqual(rows["臺北市大安區"], 0)

    def test_cost_index_minmax_scaled_to_50_100(self):
        con = connect()
        con.execute("CREATE TABLE raw_land_value (district VARCHAR, land_value DOUBLE)")
        con.executemany(
            "INSERT INTO raw_land_value VALUES (?, ?)",
            [("臺北市大安區", 200.0), ("臺北市中正區", 100.0), ("臺北市士林區", 50.0)],
        )

        stage_cost(con)
        rows = dict(
            con.execute("SELECT district, real_estate_cost_index FROM stg_cost ORDER BY district").fetchall()
        )

        self.assertAlmostEqual(rows["臺北市大安區"], 100.0)  # max
        self.assertAlmostEqual(rows["臺北市士林區"], 50.0)   # min
        self.assertAlmostEqual(rows["臺北市中正區"], 50.0 + 50.0 * ((100 - 50) / (200 - 50)))

    def test_cost_index_equal_values_returns_75(self):
        con = connect()
        con.execute("CREATE TABLE raw_land_value (district VARCHAR, land_value DOUBLE)")
        con.executemany("INSERT INTO raw_land_value VALUES (?, ?)",
                        [("臺北市大安區", 120.0), ("臺北市中正區", 120.0)])
        stage_cost(con)
        rows = dict(con.execute("SELECT district, real_estate_cost_index FROM stg_cost").fetchall())
        self.assertAlmostEqual(rows["臺北市大安區"], 75.0)
        self.assertAlmostEqual(rows["臺北市中正區"], 75.0)


class FeatureMartTests(unittest.TestCase):
    def test_mart_joins_and_drops_unresolved(self):
        con = connect()
        con.execute("CREATE TABLE stg_stations (station_name VARCHAR, monthly_entries_exits DOUBLE)")
        con.executemany("INSERT INTO stg_stations VALUES (?, ?)",
                        [("A", 100.0), ("B", 50.0), ("Ghost", 10.0)])
        con.execute("CREATE TABLE stg_entrances (station_name VARCHAR, lon DOUBLE, lat DOUBLE)")
        con.executemany("INSERT INTO stg_entrances VALUES (?, ?, ?)",
                        [("A", 0, 0), ("A", 0, 0), ("B", 0, 0)])  # A:2 entrances, B:1
        con.execute("CREATE TABLE stg_station_district (station_name VARCHAR, district VARCHAR)")
        con.executemany("INSERT INTO stg_station_district VALUES (?, ?)",
                        [("A", "臺北市大安區"), ("B", "臺北市中正區")])  # Ghost unresolved
        con.execute("CREATE TABLE stg_competitors (district VARCHAR, competitor_count BIGINT)")
        con.executemany("INSERT INTO stg_competitors VALUES (?, ?)",
                        [("臺北市大安區", 300), ("臺北市中正區", 100)])
        con.execute("CREATE TABLE stg_population (district VARCHAR, target_population BIGINT)")
        con.executemany("INSERT INTO stg_population VALUES (?, ?)",
                        [("臺北市大安區", 40000), ("臺北市中正區", 30000)])
        con.execute("CREATE TABLE stg_cost (district VARCHAR, real_estate_cost_index DOUBLE)")
        con.executemany("INSERT INTO stg_cost VALUES (?, ?)",
                        [("臺北市大安區", 100.0), ("臺北市中正區", 60.0)])

        dropped = build_feature_mart(con)
        rows = con.execute(
            "SELECT station_name, monthly_entries_exits, target_population, competitor_count, "
            "real_estate_cost_index, transport_access_index FROM mart_station_features "
            "ORDER BY station_name"
        ).fetchall()

        self.assertEqual(dropped, 1)  # Ghost dropped
        self.assertEqual(
            rows,
            [
                ("A", 100.0, 40000, 300, 100.0, 1.0),   # 2 entrances -> max -> 1.0
                ("B", 50.0, 30000, 100, 60.0, 0.5),     # 1 entrance -> 0.5
            ],
        )


if __name__ == "__main__":
    unittest.main()
