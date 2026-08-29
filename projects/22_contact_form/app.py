import os
import re
import logging
from pathlib import Path

import requests
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify

from _shared.csrf_setup import init_csrf
from _shared.errors import get as err

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent

load_dotenv()
bp = Blueprint("contact_form", __name__, template_folder=str(BASE_DIR / "templates"), static_folder=str(BASE_DIR / "static"))

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

TOOLS = [
    "02 Web記事要約ツール",
    "03 YouTube要約ツール",
    "04 メルカリ出品文生成ツール",
    "05 AliExpress価格監視ツール",
    "07 メモアプリ（認証付き）",
    "08 外部API連携ハブ",
    "09 毎朝Discordお知らせBot",
    "10 家計簿ダッシュボード",
    "11 GitHub→Discord Webhook中継",
    "13 競合調査ツール",
    "14 SEO記事生成ツール",
    "15 SNS統合管理ツール",
    "16 広告文生成ツール",
    "17 問い合わせ管理CRM",
    "18 補助金マッチング＆事業計画ドラフト生成",
    "19 接客・クレーム対応ロールプレイAI",
    "20 音声入力式 日報・引継ぎ自動整形",
    "21 写真ベース 衛生点検・HACCP記録サポート",
    "23 店舗改善インサイトダッシュボード",
    "24 シフト作成アシスタントAI",
    "25 業務マニュアル・SOP自動生成",
    "26 在庫発注タイミング予測AI",
    "27 求人原稿・面接質問自動生成",
    "28 QRコード名刺メーカー",
    "29 Webフォーム→Notion自動転記Bot",
    "30 リアルタイム為替・株価モニター",
    "31 画像→テキスト OCR変換ツール",
    "32 Googleカレンダー連携 予定要約Bot",
    "33 Markdown→スライド自動生成",
    "34 多言語リアルタイム翻訳チャット",
    "35 CSVデータ 対話型分析ツール",
    "36 ブラウザ拡張連携 クリップボード自動整形",
    "37 LINE Bot→タスク管理連携",
    "その他・全体について",
]


@bp.route("/")
def index():
    selected_tool = request.args.get("tool", "")
    return render_template("contact_form/index.html", tools=TOOLS, selected_tool=selected_tool)


@bp.route("/api/submit", methods=["POST"])
def api_submit():
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    company = (data.get("company") or "").strip()
    email = (data.get("email") or "").strip()
    tools = data.get("tools") or []
    message = (data.get("message") or "").strip()

    if not name or len(name) > 50:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if len(company) > 100:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if not email or len(email) > 100 or not EMAIL_RE.match(email):
        return jsonify({"ok": False, "error": "メールアドレスの形式を確認してください"}), 400
    if not message or len(message) > 1000:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if not isinstance(tools, list) or len(tools) > len(TOOLS) or any(t not in TOOLS for t in tools):
        return jsonify({"ok": False, "error": err("invalid_input")}), 400

    # Vercelの環境変数設定でBOM(U+FEFF)が混入することがあるため除去する
    webhook_url = (os.environ.get("DISCORD_WEBHOOK_URL") or "").strip().lstrip("﻿")
    if not webhook_url:
        return jsonify({"ok": False, "error": err("missing_discord")}), 500

    embed = {
        "title": "📩 ポートフォリオへのお問い合わせ",
        "color": 0x4F46E5,
        "fields": [
            {"name": "お名前", "value": name, "inline": True},
            {"name": "会社名", "value": company or "（未入力）", "inline": True},
            {"name": "メールアドレス", "value": email, "inline": False},
            {"name": "ご相談のツール", "value": "\n".join(tools) or "（未選択）", "inline": False},
            {"name": "ご相談内容", "value": message[:1000], "inline": False},
        ],
    }

    try:
        res = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
        if res.status_code not in (200, 204):
            logger.error("discord webhook failed: %s %s", res.status_code, res.text)
            return jsonify({"ok": False, "error": err("internal_error")}), 500
    except requests.RequestException:
        logger.exception("discord webhook request failed")
        return jsonify({"ok": False, "error": err("internal_error")}), 500

    return jsonify({"ok": True})


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5022)
