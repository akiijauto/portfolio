import sys
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf

from fetchers import fetch_weather, fetch_exchange, fetch_news, CURRENCIES

load_dotenv()

bp = Blueprint("api_hub", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template("api_hub/index.html", currencies=CURRENCIES)


@bp.route("/api/weather", methods=["POST"])
def api_weather():
    city = request.form.get("city", "").strip()
    if not city:
        return jsonify({"ok": False, "error": "都市名を入力してください。"}), 400
    if len(city) > 100:
        return jsonify({"ok": False, "error": "都市名は100文字以内で入力してください。"}), 400
    return jsonify(fetch_weather(city))


@bp.route("/api/exchange", methods=["POST"])
def api_exchange():
    from_ = request.form.get("from", "USD").upper().strip()
    to = request.form.get("to", "JPY").upper().strip()
    try:
        amount = float(request.form.get("amount", 1))
        if amount <= 0:
            raise ValueError
    except ValueError:
        return jsonify({"ok": False, "error": "金額には正の数を入力してください。"}), 400
    if from_ == to:
        return jsonify({"ok": False, "error": "変換元と変換先に同じ通貨を選択しています。"}), 400
    return jsonify(fetch_exchange(from_, to, amount))


@bp.route("/api/news", methods=["POST"])
def api_news():
    return jsonify(fetch_news())


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5008)
