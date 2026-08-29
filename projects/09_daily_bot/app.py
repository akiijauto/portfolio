import sys
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf

from scheduler import run_digest, get_logs, get_job_info, set_schedule, remove_schedule

load_dotenv()

bp = Blueprint("daily_bot", __name__, template_folder="templates", static_folder="static")

# アプリ起動時にスケジューラを初期化（デフォルト 08:00 JST）
# 定期配信は停止中。再開する場合は画面のスケジュール設定から明示的に登録する。


@bp.route("/")
def index():
    job = get_job_info()
    logs = get_logs()
    return render_template("daily_bot/index.html", job=job, logs=logs)


@bp.route("/api/run", methods=["POST"])
def api_run():
    result = run_digest()
    return jsonify(result)


@bp.route("/api/schedule", methods=["POST"])
def api_schedule():
    time_str = request.form.get("time", "08:00").strip()
    try:
        parts = time_str.split(":")
        hour = int(parts[0])
        minute = int(parts[1]) if len(parts) > 1 else 0
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except (ValueError, IndexError):
        return jsonify({"ok": False, "error": "時刻の形式が正しくありません（例：08:00）"}), 400

    set_schedule(hour, minute)
    job = get_job_info()
    return jsonify({"ok": True, "next_run": job["next_run"]})


@bp.route("/api/schedule", methods=["DELETE"])
def api_schedule_delete():
    remove_schedule()
    return jsonify({"ok": True})


@bp.route("/api/status")
def api_status():
    return jsonify({"job": get_job_info(), "logs": get_logs()})


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5009)
