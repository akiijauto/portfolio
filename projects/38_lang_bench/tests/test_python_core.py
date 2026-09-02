"""Python実装がゴールデン期待値と一致することの回帰テスト。

Python は期待値の生成元（リファレンス）なので、このテストが検出するのは
「core.py を変えたのに golden.json を再生成し忘れた」という取り違えである。
Go/Ruby のテストが落ちているのに Python だけ通る、という事故を防ぐ。
"""

import json
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "python"))

from core import ValidationError, compute, discount_rate, round2  # noqa: E402


class TestGoldenParity(unittest.TestCase):
    def setUp(self):
        path = ROOT / "tests" / "golden.json"
        if not path.exists():
            self.skipTest("golden.json が無い（harness/gen_golden.py で生成する）")
        self.golden = json.loads(path.read_text(encoding="utf-8"))

    def test_golden_parity(self):
        self.assertTrue(self.golden["cases"], "golden.json にケースが無い")
        for case in self.golden["cases"]:
            with self.subTest(case["name"]):
                got = compute(case["request"])
                got.pop("lang")
                self.assertEqual(case["expect"], got)


class TestRounding(unittest.TestCase):
    def test_half_away_from_zero(self):
        """Pythonの組み込み round() は偶数丸め。Go/Ruby と揃うことを明示的に固定する。"""
        self.assertEqual(round2(2.675), 2.68)
        self.assertEqual(round2(0.125), 0.13)
        self.assertEqual(round2(-0.125), -0.13)


class TestDiscountRate(unittest.TestCase):
    def test_table(self):
        self.assertEqual(discount_rate("gold", 0), 0.12)
        self.assertEqual(discount_rate("silver", 0), 0.07)
        self.assertEqual(discount_rate("platinum", 0), 0.02)

    def test_long_history_bonus_and_cap(self):
        self.assertAlmostEqual(discount_rate("gold", 365), 0.15)
        self.assertAlmostEqual(discount_rate("bronze", 400), 0.05)
        self.assertLessEqual(discount_rate("gold", 100000), 0.20)


class TestValidation(unittest.TestCase):
    def test_rejects_bad_input(self):
        invalid = {
            "order_id無し": {"items": [{"sku": "A", "qty": 1, "unit_price": 1}]},
            "明細が空": {"order_id": "X", "items": []},
            "数量ゼロ": {"order_id": "X", "items": [{"sku": "A", "qty": 0, "unit_price": 1}]},
            "負の単価": {"order_id": "X", "items": [{"sku": "A", "qty": 1, "unit_price": -1}]},
        }
        for name, req in invalid.items():
            with self.subTest(name):
                with self.assertRaises(ValidationError):
                    compute(req)


if __name__ == "__main__":
    unittest.main()
