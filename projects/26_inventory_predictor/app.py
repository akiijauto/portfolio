import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify

import generator

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import handle_ai_error
from shared.errors import get as err

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
bp = Blueprint("inventory_predictor", __name__, template_folder="templates", static_folder="static")

MAX_ITEMS = 30


@bp.route("/")
def index():
    return render_template("inventory_predictor/index.html")


@bp.route("/api/predict", methods=["POST"])
def api_predict():
    data = request.get_json(silent=True) or {}
    items = data.get("items")
    notes = (data.get("notes") or "").strip()

    if not isinstance(items, list) or not items or len(items) > MAX_ITEMS:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if len(notes) > 1000:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400

    for it in items:
        if not isinstance(it, dict):
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
        name = it.get("name")
        if not isinstance(name, str) or not name:
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
        for key in ("current_stock", "avg_daily_usage", "lead_time_days", "order_lot"):
            v = it.get(key)
            if not isinstance(v, (int, float)) or v < 0:
                return jsonify({"ok": False, "error": err("invalid_input")}), 400

    try:
        result = generator.predict_reorder(items, notes)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.exception("inventory prediction failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "inventory-predictor")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5026)
