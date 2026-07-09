import unittest

from importers import parse_csv_bytes


class TestImporters(unittest.TestCase):
    def test_parse_csv_success(self):
        data = (
            "日期,金额,类型明细,交易方向,日记,类型,旅游标识,旅游标签\n"
            "2025-10-01,34.22,吃,支出,周三跨年,食品饮料,0,\n"
            "2025-10-22,512,轮渡,支出,国庆烟台返程,交通,1,烟台国庆\n"
        ).encode("utf-8")
        rows, err = parse_csv_bytes(data)
        self.assertEqual(err, "")
        self.assertEqual(len(rows), 2)
        self.assertTrue(rows[0]["is_valid"])
        self.assertTrue(rows[1]["is_travel"])

    def test_parse_csv_missing_column(self):
        data = "日期,金额,类型明细\n2025-10-01,34.22,吃\n".encode("utf-8")
        rows, err = parse_csv_bytes(data)
        self.assertEqual(rows, [])
        self.assertIn("缺少必填字段", err)


if __name__ == "__main__":
    unittest.main()
