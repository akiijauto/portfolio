import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify
import generator

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.errors import get as err
from shared.utils import handle_ai_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
bp = Blueprint("ad_copy_generator", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template(
        "ad_copy_generator/index.html",
        goals=list(generator.GOALS.keys()),
    )


@bp.route("/generate", methods=["POST"])
def generate():
    product  = request.form.get("product",  "").strip()
    target   = request.form.get("target",   "").strip()
    usp      = request.form.get("usp",      "").strip()
    industry = request.form.get("industry", "").strip()
    goal     = request.form.get("goal",     "リード獲得")

    if not product or not target or not usp:
        return jsonify({"ok": False, "error": "商品名・ターゲット・強みはすべて必須です"}), 400
    if len(product) > 100 or len(target) > 100 or len(usp) > 300:
        return jsonify({"ok": False, "error": "入力が長すぎます"}), 400
    if goal not in generator.GOALS:
        goal = "リード獲得"

    try:
        data = generator.generate_all(product, target, usp, industry, goal)
        return jsonify({"ok": True, **data})
    except Exception as e:
        logger.exception("ad generation failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "ad-copy-generator")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5016)
