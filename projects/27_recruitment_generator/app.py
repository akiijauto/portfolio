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
bp = Blueprint("recruitment_generator", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template("recruitment_generator/index.html")


@bp.route("/api/generate", methods=["POST"])
def api_generate():
    data = request.get_json(silent=True) or {}
    position = (data.get("position") or "").strip()
    employment_type = (data.get("employment_type") or "").strip()
    work_schedule = (data.get("work_schedule") or "").strip()
    salary = (data.get("salary") or "").strip()
    job_description = (data.get("job_description") or "").strip()
    ideal_candidate = (data.get("ideal_candidate") or "").strip()
    appeal_points = (data.get("appeal_points") or "").strip()

    required_fields = {
        "position": position,
        "employment_type": employment_type,
        "work_schedule": work_schedule,
        "salary": salary,
    }
    for value in required_fields.values():
        if not value or len(value) > 500:
            return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if not job_description or len(job_description) > 1000:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    if len(ideal_candidate) > 500 or len(appeal_points) > 500:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400

    try:
        result = generator.generate_recruitment(
            position, employment_type, work_schedule, salary,
            job_description, ideal_candidate, appeal_points,
        )
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.exception("recruitment generation failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "recruitment-generator")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5027)
