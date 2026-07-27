import unittest

from rule_manager import (
    infer_category,
    is_known_category,
    is_known_l1,
    l2_to_l1,
    learn_exact_detail,
    category_options_grouped,
    l1_options,
    l2_options,
)


class TestRuleManager(unittest.TestCase):
    def test_infer_known(self):
        l1, l2 = infer_category("午餐", is_income=False)
        self.assertTrue(isinstance(l1, str) and len(l1) > 0)
        self.assertEqual(l1, l2)

    def test_is_known_category(self):
        self.assertTrue(is_known_category("工资", is_income=True))
        self.assertTrue(is_known_category("待分类收入", is_income=True))
        self.assertFalse(is_known_category("不存在的类型XYZ", is_income=False))

    def test_is_known_l1(self):
        self.assertTrue(is_known_l1("食品饮料", is_income=False))
        self.assertTrue(is_known_l1("生活支出", is_income=False))
        self.assertFalse(is_known_l1("不存在L1", is_income=False))

    def test_l2_to_l1_legacy(self):
        # 旧二级名映射到一级；单层后已知类型返回自身
        self.assertEqual(l2_to_l1("医药", is_income=False), "生活支出")
        self.assertEqual(l2_to_l1("VPN", is_income=False), "虚拟充值/通讯")
        self.assertEqual(l2_to_l1("工资", is_income=True), "工资")
        self.assertEqual(l2_to_l1("不存在的L2", is_income=False), "")

    def test_infer_returns_single_level(self):
        result = infer_category("中药", is_income=False)
        self.assertIsInstance(result, tuple)
        self.assertEqual(len(result), 2)
        l1, l2 = result
        self.assertEqual(l1, "生活支出")
        self.assertEqual(l2, "生活支出")

    def test_learn_exact_detail(self):
        detail = "自动化测试-新明细-仅测试-单层"
        ok = learn_exact_detail(detail, "生活支出", is_income=False)
        self.assertIn(ok, (True, False))
        l1, l2 = infer_category(detail, is_income=False)
        self.assertEqual(l1, "生活支出")
        self.assertEqual(l2, "生活支出")

    def test_grouped_options(self):
        groups = category_options_grouped(is_income=False)
        self.assertTrue(len(groups) > 0)
        for g in groups:
            self.assertIn("l1", g)
            self.assertIn("l2s", g)
            self.assertEqual(g["l2s"], [g["l1"]])

    def test_l1_l2_options(self):
        l1s = l1_options(is_income=False)
        self.assertIn("生活支出", l1s)
        self.assertIn("虚拟充值/通讯", l1s)
        # 单层后 l2_options 即全部类型名
        l2s = l2_options(is_income=False, l1="生活支出")
        self.assertIn("生活支出", l2s)
        self.assertNotIn("医药", l2s)


if __name__ == "__main__":
    unittest.main()
