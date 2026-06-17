import unittest

from retail_scout.pipeline import normalize_station_name, normalize_taipei_name


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


if __name__ == "__main__":
    unittest.main()
