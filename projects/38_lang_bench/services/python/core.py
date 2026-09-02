"""SPEC-API-v1 のスコアリング計算（Python実装）。

HTTP層から意図的に切り離してある。3言語が「同じ仕事」をしていることを
テストで機械的に保証するのがこのモジュールの役割で、ここが食い違うと
性能比較の数値そのものが無意味になる。変更時は必ず3実装を同時に直し、
tests/golden.json での検証を通すこと。
"""

import hashlib
import math


class ValidationError(ValueError):
    """リクエスト内容の不備。HTTP層で400に変換する。"""


def round2(value: float) -> float:
    """Go の math.Round / Ruby の Float#round と同じ「0.5は絶対値の大きい側へ」。

    組み込みの round() は偶数丸めなので、そのまま使うと3実装で金額が食い違う。
    """
    if value >= 0:
        return math.floor(value * 100 + 0.5) / 100
    return -(math.floor(-value * 100 + 0.5) / 100)


def discount_rate(tier: str, history_days: int) -> float:
    """SPEC-API-v1の割引表。3実装で同一の値を返さなければならない。"""
    rate = {"gold": 0.12, "silver": 0.07}.get(tier, 0.02)
    if history_days >= 365:
        rate += 0.03
    return min(rate, 0.20)


def signature(order_id: str, subtotal: float, rounds: int) -> str:
    """注文の改ざん検知署名を模したCPU負荷。SHA-256をrounds回チェーンする。

    rounds を上げるとCPU比重が、明細数を上げるとJSON/メモリ比重が増える。
    """
    digest = hashlib.sha256(f"{order_id}|{subtotal:.2f}".encode()).digest()
    for _ in range(rounds):
        digest = hashlib.sha256(digest).digest()
    return digest.hex()


def compute(req: dict) -> dict:
    order_id = req.get("order_id") or ""
    items = req.get("items") or []
    if not order_id or not items:
        raise ValidationError("validation_failed")

    subtotal = 0.0
    for it in items:
        qty = it.get("qty", 0)
        unit_price = it.get("unit_price", 0.0)
        if qty <= 0 or unit_price < 0:
            raise ValidationError("validation_failed")
        subtotal += qty * unit_price
    subtotal = round2(subtotal)

    customer = req.get("customer") or {}
    rate = discount_rate(customer.get("tier", ""), customer.get("history_days", 0))
    discount = round2(subtotal * rate)
    tax = round2((subtotal - discount) * 0.10)
    total = round2(subtotal - discount + tax)

    # 上位SKU抽出。金額降順、同額はSKU昇順で3実装の結果を一致させる。
    ranked = sorted(items, key=lambda it: (-(it["qty"] * it["unit_price"]), it["sku"]))
    top_skus = [it["sku"] for it in ranked[:5]]

    rounds = req.get("rounds") or 0
    if rounds <= 0:
        rounds = 200

    return {
        "order_id": order_id,
        "lang": "python",
        "item_count": len(items),
        "subtotal": subtotal,
        "discount": discount,
        "tax": tax,
        "total": total,
        "signature": signature(order_id, subtotal, rounds),
        "top_skus": top_skus,
        "rounds": rounds,
    }
