import sys
import os
import logging
import requests as req
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
from flask import Flask, render_template, request, jsonify, redirect, url_for
from storage import get_all, add_product, update_price, delete_product, get_by_id
from scraper import fetch_price
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.errors import get as err

logger = logging.getLogger(__name__)

load_dotenv()

app = Flask(__name__, template_folder="templates", static_folder="static")

# ── Discord通知 ──────────────────────────────────────────────────────
def notify_discord(product: dict, old_price: float):
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook:
        return
    drop = old_price - product["current_price"]
    pct  = drop / old_price * 100
    req.post(webhook, json={"embeds": [{
        "title": f"💰 価格下落通知: {product['name']}",
        "description": (
            f"**{old_price:,.0f}円 → {product['current_price']:,.0f}円**\n"
            f"▼ {drop:,.0f}円 ({pct:.1f}%) 値下がり\n\n"
            f"[商品を見る]({product['url']})"
        ),
        "color": 3066993
    }]})

# ── スケジューラー（毎日9時に全商品チェック）────────────────────────
def daily_check():
    print(f"[{datetime.now().strftime('%H:%M')}] 定期価格チェック開始")
    for p in get_all():
        try:
            old   = p["current_price"]
            price = fetch_price(p["url"])
            updated = update_price(p["id"], price)
            if old and price < old:
                notify_discord(updated, old)
                print(f"  値下がり通知送信: {p['name']}")
            print(f"  {p['name']}: {price:,.0f}円")
        except Exception as e:
            print(f"  エラー({p['name']}): {e}")

# 毎日9時の自動チェックは停止済み（2026-07-30、SNS投稿通知チャンネルへの
# 日次サマリー混在を避けるため）。手動チェック（/check, /check_all）は引き続き利用可能。
scheduler = BackgroundScheduler()
scheduler.start()

# ── ルート ──────────────────────────────────────────────────────────
@app.route("/")
def index():
    products = get_all()
    return render_template("index.html", products=products,
                           now=datetime.now().strftime("%Y-%m-%d %H:%M"))

@app.route("/add", methods=["POST"])
def add():
    url    = request.form.get("url", "").strip()
    name   = request.form.get("name", "").strip()
    target = request.form.get("target_price", "").strip()
    if not url or not name:
        return jsonify({"ok": False, "error": "URLと商品名を入力してください"}), 400
    target_price = float(target) if target else None
    product = add_product(url, name, target_price)
    return jsonify({"ok": True, "id": product["id"]})

@app.route("/check/<product_id>", methods=["POST"])
def check(product_id):
    """今すぐ価格チェック"""
    p = get_by_id(product_id)
    if not p:
        return jsonify({"ok": False, "error": "商品が見つかりません"}), 404
    try:
        old   = p["current_price"]
        price = fetch_price(p["url"])
        updated = update_price(product_id, price)
        if old and price < old:
            notify_discord(updated, old)
        return jsonify({"ok": True, "price": price, "status": updated["status"]})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": err("fetch_failed")}), 500

@app.route("/manual/<product_id>", methods=["POST"])
def manual(product_id):
    """手動価格入力"""
    try:
        price   = float(request.form.get("price", 0))
        if price <= 0:
            return jsonify({"ok": False, "error": "価格は0より大きい値を入力してください"}), 400
        p       = get_by_id(product_id)
        old     = p["current_price"] if p else None
        updated = update_price(product_id, price)
        if old and price < old:
            notify_discord(updated, old)
        return jsonify({"ok": True, "price": price, "status": updated["status"]})
    except Exception as e:
        logger.exception("manual price update failed: product_id=%s", product_id)
        return jsonify({"ok": False, "error": err("internal_error")}), 500

@app.route("/delete/<product_id>", methods=["POST"])
def delete(product_id):
    delete_product(product_id)
    return jsonify({"ok": True})

@app.route("/check_all", methods=["POST"])
def check_all():
    daily_check()
    return jsonify({"ok": True})

if __name__ == "__main__":
    app.run(debug=False, port=5005)
