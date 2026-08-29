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
bp = Blueprint("voice_report", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template("voice_report/index.html")


@bp.route("/api/format", methods=["POST"])
def api_format():
    data = request.get_json(silent=True) or {}
    raw_text = (data.get("raw_text") or "").strip()
    staff_name = (data.get("staff_name") or "").strip()
    report_date = (data.get("report_date") or "").strip()

    if not raw_text:
        return jsonify({"ok": False, "error": "日報の内容を入力してください"}), 400
    if len(raw_text) > 3000:
        return jsonify({"ok": False, "error": "3000文字以内で入力してください"}), 400
    if len(staff_name) > 50 or len(report_date) > 50:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400

    try:
        result = generator.format_report(raw_text, staff_name, report_date)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.exception("voice report formatting failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "voice-report")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5020)
