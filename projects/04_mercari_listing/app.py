import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify
from generator import generate_listing, CONDITIONS

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.errors import get as err
from shared.utils import handle_ai_error

load_dotenv()

bp = Blueprint("mercari_listing", __name__, template_folder="templates", static_folder="static")

@bp.route("/")
def index():
    return render_template("mercari_listing/index.html", conditions=list(CONDITIONS.keys()))

@bp.route("/generate", methods=["POST"])
def generate():
    name      = request.form.get("name", "").strip()
    condition = request.form.get("condition", "").strip()
    category  = request.form.get("category", "").strip()
    features  = request.form.get("features", "").strip()

    if not name:
        return jsonify({"ok": False, "error": "商品名を入力してください"}), 400
    if not condition:
        return jsonify({"ok": False, "error": "商品の状態を選択してください"}), 400
    try:
        result = generate_listing(name, condition, category, features)
        return jsonify({"ok": True, "data": result})
    except Exception as e:
        return jsonify({"ok": False, "error": handle_ai_error(e, "mercari-listing-ai")}), 500

def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5004)
