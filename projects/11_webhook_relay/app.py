import sys
import os
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, jsonify, render_template, request, url_for

sys.path.insert(0, str(Path(__file__).parents[2]))

from webhook import get_logs, handle_event, verify_signature

load_dotenv()

bp = Blueprint("webhook_relay", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    webhook_url = url_for(".github_webhook", _external=True)
    return render_template("webhook_relay/index.html", logs=get_logs(), webhook_url=webhook_url)


@bp.route("/webhook/github", methods=["POST"])
def github_webhook():
    payload_bytes = request.get_data()
    sig = request.headers.get("X-Hub-Signature-256", "")
    if not verify_signature(payload_bytes, sig):
        return jsonify({"error": "signature mismatch"}), 403

    event_type = request.headers.get("X-GitHub-Event", "unknown")
    try:
        payload = request.get_json(force=True) or {}
    except Exception:
        payload = {}

    status_code, message = handle_event(event_type, payload)
    return jsonify({"status": message}), status_code


@bp.route("/api/logs")
def api_logs():
    return jsonify(get_logs())


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.config["WTF_CSRF_ENABLED"] = False  # フォームなし・外部Webhook受信のみ
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5011)
