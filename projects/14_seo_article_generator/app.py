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
bp = Blueprint("seo_article_generator", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template(
        "seo_article_generator/index.html",
        article_types=list(generator.ARTICLE_TYPES.keys()),
        tones=list(generator.TONES.keys()),
    )


@bp.route("/outline", methods=["POST"])
def outline():
    keyword = request.form.get("keyword", "").strip()
    article_type = request.form.get("article_type", "解説記事")
    tone = request.form.get("tone", "丁寧（です/ます体）")
    competitor_context = request.form.get("competitor_context", "")
    try:
        target_chars = max(500, min(int(request.form.get("target_chars", 2000)), 5000))
    except ValueError:
        target_chars = 2000

    if not keyword:
        return jsonify({"ok": False, "error": "キーワードを入力してください"}), 400
    if len(keyword) > 200:
        return jsonify({"ok": False, "error": "200文字以内で入力してください"}), 400
    if article_type not in generator.ARTICLE_TYPES:
        article_type = "解説記事"
    if tone not in generator.TONES:
        tone = "丁寧（です/ます体）"

    try:
        data = generator.generate_outline(keyword, article_type, tone,
                                          target_chars, competitor_context)
        return jsonify({"ok": True, "outline": data})
    except Exception as e:
        logger.exception("outline generation failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "seo-article-generator")}), 500


@bp.route("/generate", methods=["POST"])
def generate():
    keyword = request.form.get("keyword", "").strip()
    outline_json = request.form.get("outline", "{}")
    tone = request.form.get("tone", "丁寧（です/ます体）")
    try:
        target_chars = max(500, min(int(request.form.get("target_chars", 2000)), 5000))
    except ValueError:
        target_chars = 2000

    if not keyword:
        return jsonify({"ok": False, "error": "キーワードがありません"}), 400

    import json
    try:
        outline = json.loads(outline_json)
    except Exception:
        return jsonify({"ok": False, "error": "アウトラインが不正です"}), 400

    try:
        article = generator.generate_article(keyword, outline, tone, target_chars)
        char_count = len(article)
        return jsonify({"ok": True, "article": article, "char_count": char_count})
    except Exception as e:
        logger.exception("article generation failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "seo-article-generator")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5014)
