import base64
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify

import generator
from generator import CATEGORIES

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import handle_ai_error
from shared.errors import get as err

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
bp = Blueprint("haccp_inspection", __name__, template_folder="templates", static_folder="static")

MAX_IMAGE_BYTES = 5 * 1024 * 1024
ALLOWED_MEDIA_TYPES = {"image/jpeg", "image/png", "image/webp"}


@bp.route("/")
def index():
    return render_template(
        "haccp_inspection/index.html",
        categories=[{"id": k, "label": v} for k, v in CATEGORIES.items()],
    )


@bp.route("/api/inspect", methods=["POST"])
def api_inspect():
    category = request.form.get("category", "")
    notes = (request.form.get("notes") or "").strip()

    if category not in CATEGORIES:
        return jsonify({"ok": False, "error": "点検カテゴリを選択してください"}), 400
    if len(notes) > 300:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400

    image = request.files.get("image")
    if not image or not image.filename:
        return jsonify({"ok": False, "error": "点検対象の写真をアップロードしてください"}), 400
    if image.mimetype not in ALLOWED_MEDIA_TYPES:
        return jsonify({"ok": False, "error": "JPEG・PNG・WebP形式の画像をアップロードしてください"}), 400

    image_bytes = image.read()
    if len(image_bytes) > MAX_IMAGE_BYTES:
        return jsonify({"ok": False, "error": "画像サイズは5MB以内にしてください"}), 400

    image_b64 = base64.b64encode(image_bytes).decode("ascii")

    try:
        result = generator.inspect_photo(image_b64, image.mimetype, category, notes)
        return jsonify({"ok": True, "result": result, "category_label": CATEGORIES[category]})
    except Exception as e:
        logger.exception("haccp inspection failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "haccp-inspection")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5021)
