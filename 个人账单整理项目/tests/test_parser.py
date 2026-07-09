import unittest

from parser import ImportOptions, ParseOptions, parse_bill_text, parse_for_staging, summarize


SAMPLE_TEXT = """1-01；周三跨年
电脑键盘保护膜；12.0；生活支出
奖学金；600；收入；工资

1-02；
午餐；72；食品饮料
"""


class TestParser(unittest.TestCase):
    def test_parse_core_fields(self):
        records = parse_bill_text(SAMPLE_TEXT, ParseOptions(year=2025))
        self.assertEqual(len(records), 3)
        self.assertIn("年月", records[0])
        self.assertEqual(records[0]["日期"], "2025-01-01")
        self.assertIn("一级类型", records[0])

    def test_direction_and_summary(self):
        records = parse_bill_text(SAMPLE_TEXT, ParseOptions(year=2025))
        stats = summarize(records)
        self.assertAlmostEqual(stats["total_income"], 600.0)
        self.assertAlmostEqual(stats["total_expense"], 84.0)
        self.assertAlmostEqual(stats["net"], 516.0)

    def test_travel_tag_and_keyword(self):
        txt = """10-01；旅游标签-（烟台）回程
轮渡；512；交通

10-02；普通日
酒店；200；住宿
"""
        rows = parse_for_staging(
            txt,
            ImportOptions(year=2025, travel_keywords="轮渡,机票", mark_all_travel=False),
        )
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["is_travel"])
        self.assertEqual(rows[0]["travel_tag"], "烟台")
        self.assertFalse(rows[1]["is_travel"])

    def test_unmatched_category_marked_pending(self):
        txt = """10-10；普通日
完全未知消费词；12； 
"""
        rows = parse_for_staging(txt, ImportOptions(year=2025))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "待分类")
        self.assertEqual(rows[0]["category_l1"], "待分类")

    def test_import_year_fills_mmdd(self):
        txt = """12-31；跨年测
一笔；1；
"""
        rows = parse_for_staging(txt, ImportOptions(year=1999))
        self.assertEqual(rows[0]["bill_date"], "1999-12-31")

    def test_explicit_category_not_in_dict_flagged(self):
        txt = """5-01；陈年补录
某物；10；陈年老类型不在字典
"""
        rows = parse_for_staging(txt, ImportOptions(year=2018))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0].get("category_unknown"))
        self.assertEqual(rows[0]["explicit_category_raw"], "陈年老类型不在字典")
        self.assertEqual(rows[0]["category"], "陈年老类型不在字典")

    def test_infer_returns_l1_and_l2(self):
        txt = """3-15；测试日
午餐；50；
"""
        rows = parse_for_staging(txt, ImportOptions(year=2025))
        self.assertEqual(len(rows), 1)
        self.assertTrue(rows[0]["category_l1"])
        self.assertTrue(rows[0]["category"])
        self.assertNotIn(rows[0]["category"], ("待分类", ""))

    def test_explicit_known_l2_sets_l1(self):
        txt = """6-01；测L1
药方；30；医药
"""
        rows = parse_for_staging(txt, ImportOptions(year=2025))
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["category"], "医药")
        self.assertEqual(rows[0]["category_l1"], "生活支出")
        self.assertFalse(rows[0].get("category_unknown"))


if __name__ == "__main__":
    unittest.main()
