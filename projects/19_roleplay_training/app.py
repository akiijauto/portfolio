import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify

import generator
from generator import SCENARIOS, DIFFICULTIES

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import handle_ai_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
bp = Blueprint("roleplay_training", __name__, template_folder="templates", static_folder="static")

MAX_TURNS = 8


@bp.route("/")
def index():
    return render_template(
        "roleplay_training/index.html",
        scenarios=[{"id": k, **v} for k, v in SCENARIOS.items()],
        difficulties=DIFFICULTIES,
    )


def _validate_scenario(data):
    scenario = data.get("scenario", "")
    difficulty = data.get("difficulty", "normal")
    if scenario not in SCENARIOS:
        return None, None, "シナリオを選択してください"
    if difficulty not in DIFFICULTIES:
        difficulty = "normal"
    return scenario, difficulty, None


@bp.route("/api/start", methods=["POST"])
def api_start():
    data = request.get_json(silent=True) or {}
    scenario, difficulty, err_msg = _validate_scenario(data)
    if err_msg:
        return jsonify({"ok": False, "error": err_msg}), 400

    try:
        message = generator.start_conversation(scenario, difficulty)
        return jsonify({"ok": True, "message": message})
    except Exception as e:
        logger.exception("roleplay start failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "roleplay-training")}), 500


@bp.route("/api/reply", methods=["POST"])
def api_reply():
    data = request.get_json(silent=True) or {}
    scenario, difficulty, err_msg = _validate_scenario(data)
    if err_msg:
        return jsonify({"ok": False, "error": err_msg}), 400

    staff_message = (data.get("staff_message") or "").strip()
    if not staff_message:
        return jsonify({"ok": False, "error": "発言内容を入力してください"}), 400
    if len(staff_message) > 500:
        return jsonify({"ok": False, "error": "500文字以内で入力してください"}), 400

    history = data.get("history", [])
    if not isinstance(history, list):
        history = []
    history = history[-(MAX_TURNS * 2):]
    history.append({"speaker": "staff", "text": staff_message})

    try:
        message = generator.continue_conversation(scenario, difficulty, history)
        return jsonify({"ok": True, "message": message})
    except Exception as e:
        logger.exception("roleplay reply failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "roleplay-training")}), 500


@bp.route("/api/score", methods=["POST"])
def api_score():
    data = request.get_json(silent=True) or {}
    scenario, difficulty, err_msg = _validate_scenario(data)
    if err_msg:
        return jsonify({"ok": False, "error": err_msg}), 400

    history = data.get("history", [])
    if not isinstance(history, list) or len(history) < 2:
        return jsonify({"ok": False, "error": "会話のやり取りが少なすぎます。もう少し対話してから採点してください"}), 400

    try:
        result = generator.score_conversation(scenario, difficulty, history)
        return jsonify({"ok": True, "result": result})
    except Exception as e:
        logger.exception("roleplay scoring failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "roleplay-training")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5019)
