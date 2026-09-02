"""3言語共通の期待値ファイル tests/golden.json を生成する。

Python実装を基準（リファレンス）として期待値を作り、Go/Ruby のテストが
これに一致するかを検証する構成にしている。基準をどれか1つに固定しないと
「3つとも同じように間違っている」状態を検出できないため、
仕様変更時は必ず SPEC-API-v1（要件定義.html）を読み直してから再生成すること。
"""

import json
import pathlib
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "services" / "python"))

from core import compute  # noqa: E402

CASES = [
    {
        "name": "gold_long_history_割引上限に張り付く",
        "request": {
            "order_id": "ORD-0000001",
            "items": [
                {"sku": "SKU-0001", "qty": 3, "unit_price": 1200.55},
                {"sku": "SKU-0002", "qty": 1, "unit_price": 99.99},
                {"sku": "SKU-0003", "qty": 7, "unit_price": 45.00},
            ],
            "customer": {"tier": "gold", "history_days": 400},
            "rounds": 16,
        },
    },
    {
        "name": "silver_短期_通常割引",
        "request": {
            "order_id": "ORD-0000002",
            "items": [
                {"sku": "SKU-0100", "qty": 2, "unit_price": 5000.0},
                {"sku": "SKU-0101", "qty": 5, "unit_price": 333.33},
            ],
            "customer": {"tier": "silver", "history_days": 10},
            "rounds": 16,
        },
    },
    {
        "name": "未知tier_既定割引_端数丸めの確認",
        "request": {
            "order_id": "ORD-0000003",
            "items": [{"sku": "SKU-0200", "qty": 3, "unit_price": 0.125}],
            "customer": {"tier": "platinum", "history_days": 0},
            "rounds": 16,
        },
    },
    {
        "name": "同額SKUのタイブレーク_SKU昇順",
        "request": {
            "order_id": "ORD-0000004",
            "items": [
                {"sku": "SKU-0302", "qty": 2, "unit_price": 100.0},
                {"sku": "SKU-0301", "qty": 4, "unit_price": 50.0},
                {"sku": "SKU-0300", "qty": 1, "unit_price": 200.0},
                {"sku": "SKU-0304", "qty": 1, "unit_price": 10.0},
            ],
            "customer": {"tier": "bronze", "history_days": 365},
            "rounds": 16,
        },
    },
    {
        "name": "rounds省略時は既定の200",
        "request": {
            "order_id": "ORD-0000005",
            "items": [{"sku": "SKU-0400", "qty": 1, "unit_price": 1.0}],
            "customer": {"tier": "gold", "history_days": 0},
        },
    },
]


def main():
    out = {
        "spec": "SPEC-API-v1",
        "reference": "services/python/core.py",
        "note": "Go/Ruby のテストはこのファイルの expect と完全一致しなければならない。lang フィールドは実装ごとに異なるため比較対象外。",
        "cases": [],
    }
    for case in CASES:
        expect = compute(case["request"])
        expect.pop("lang")
        out["cases"].append({"name": case["name"], "request": case["request"], "expect": expect})

    path = ROOT / "tests" / "golden.json"
    path.write_text(json.dumps(out, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"[golden] {len(out['cases'])} ケースを {path} に書き出した")


if __name__ == "__main__":
    main()
