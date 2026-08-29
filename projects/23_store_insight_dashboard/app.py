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
bp = Blueprint("store_insight_dashboard", __name__, template_folder="templates", static_folder="static")

MAX_RECORDS = 31


@bp.route("/")
def index():
    return render_template("store_insight_dashboard/index.html")


@bp.route("/api/analyze", methods=["POST"])
def api_analyze():
    data = request.get_json(silent=True) or {}
    records = data.get("records")
    notes = (data.get("notes") or "").strip()

    if not isinstance(records, list) or not records or len(records) > MAX_RECORDS:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if len(notes) > 1000:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400

    for r in records:
        if not isinstance(r, dict):
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
        date = r.get("date")
        sales = r.get("sales")
        customers = r.get("customers")
        staff = r.get("staff")
        if not isinstance(date, str) or not date:
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
        if not all(isinstance(v, int) and v >= 0 for v in (sales, customers, staff)):
            return jsonify({"ok": False, "error": err("invalid_input")}), 400

    try:
        result = generator.analyze_insights(records, notes)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.exception("store insight analysis failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "store-insight-dashboard")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5023)
