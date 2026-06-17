import unittest

import duckdb

from retail_scout.pipeline import connect, normalize_station_name, normalize_taipei_name, stage_stations, stage_entrances, stage_station_district, stage_competitors


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


if __name__ == "__main__":
    unittest.main()
