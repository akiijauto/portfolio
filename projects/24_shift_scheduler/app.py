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
bp = Blueprint("shift_scheduler", __name__, template_folder="templates", static_folder="static")

MAX_STAFF = 20
MAX_DAYS = 7


@bp.route("/")
def index():
    return render_template("shift_scheduler/index.html")


@bp.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}
    staff = data.get("staff")
    requirements = data.get("requirements")
    notes = (data.get("notes") or "").strip()

    if not isinstance(staff, list) or not staff or len(staff) > MAX_STAFF:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if not isinstance(requirements, list) or not requirements or len(requirements) > MAX_DAYS:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if len(notes) > 1000:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400

    for s in staff:
        if not isinstance(s, dict):
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
        name = s.get("name")
        max_hours = s.get("max_hours")
        if not isinstance(name, str) or not name:
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
        if not isinstance(max_hours, int) or max_hours < 0:
            return jsonify({"ok": False, "error": err("invalid_input")}), 400

    for r in requirements:
        if not isinstance(r, dict):
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
        day = r.get("day")
        required_count = r.get("required_count")
        if not isinstance(day, str) or not day:
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
        if not isinstance(required_count, int) or required_count < 0:
            return jsonify({"ok": False, "error": err("invalid_input")}), 400

    try:
        result = generator.generate_shift(staff, requirements, notes)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.exception("shift generation failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "shift-scheduler")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5024)
