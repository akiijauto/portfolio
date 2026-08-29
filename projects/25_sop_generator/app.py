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
bp = Blueprint("sop_generator", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template("sop_generator/index.html")


@bp.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}
    task_name = (data.get("task_name") or "").strip()
    rough_steps = (data.get("rough_steps") or "").strip()
    target_audience = (data.get("target_audience") or "").strip()
    notes = (data.get("notes") or "").strip()

    if not task_name or len(task_name) > 100:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if not rough_steps or len(rough_steps) > 2000:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if not target_audience or len(target_audience) > 100:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if len(notes) > 1000:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400

    try:
        result = generator.generate_manual(task_name, rough_steps, target_audience, notes)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.exception("manual generation failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "sop-generator")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5025)
