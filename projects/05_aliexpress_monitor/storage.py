"""商品データと価格履歴をJSONで管理する。"""
import json
import uuid
from datetime import datetime
from pathlib import Path

DATA_FILE = Path(__file__).parent / "data" / "products.json"

def _load() -> dict:
    if not DATA_FILE.exists():
        return {"products": []}
    try:
        data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or "products" not in data:
            raise ValueError("不正なフォーマット")
        return data
    except (json.JSONDecodeError, ValueError):
        # ファイルが壊れている場合はバックアップして初期化
        backup = DATA_FILE.with_suffix(".json.bak")
        DATA_FILE.rename(backup)
        print(f"[警告] データファイルが壊れていたためバックアップしました: {backup}")
        return {"products": []}

def _save(data: dict):
    DATA_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def get_all() -> list:
    return _load()["products"]

def get_by_id(product_id: str) -> dict | None:
    return next((p for p in get_all() if p["id"] == product_id), None)

def add_product(url: str, name: str, target_price: float | None = None) -> dict:
    data    = _load()
    product = {
        "id":           str(uuid.uuid4()),
        "url":          url,
        "name":         name,
        "current_price": None,
        "target_price": target_price,
        "history":      [],
        "added_at":     datetime.now().isoformat(),
        "last_checked": None,
        "status":       "未チェック"
    }
    data["products"].append(product)
    _save(data)
    return product

def update_price(product_id: str, price: float) -> dict | None:
    data = _load()
    for p in data["products"]:
        if p["id"] != product_id:
            continue
        old_price = p["current_price"]
        p["current_price"] = price
        p["last_checked"]  = datetime.now().isoformat()
        p["history"].append({"date": datetime.now().strftime("%Y-%m-%d %H:%M"), "price": price})
        # 価格変動ステータス
        if old_price is None:
            p["status"] = "初回登録"
        elif price < old_price:
            p["status"] = f"値下がり（{old_price:,.0f}→{price:,.0f}円）"
        elif price > old_price:
            p["status"] = f"値上がり（{old_price:,.0f}→{price:,.0f}円）"
        else:
            p["status"] = "変化なし"
        _save(data)
        return p
    return None

def delete_product(product_id: str):
    data = _load()
    data["products"] = [p for p in data["products"] if p["id"] != product_id]
    _save(data)
