import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify
import anthropic
import analyzer

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.errors import get as err
from shared.utils import handle_ai_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
bp = Blueprint("competitor_research", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template("competitor_research/index.html")


@bp.route("/search", methods=["POST"])
def search():
    keyword = request.form.get("keyword", "").strip()
    if not keyword:
        return jsonify({"ok": False, "error": "キーワードを入力してください"}), 400
    if len(keyword) > 200:
        return jsonify({"ok": False, "error": "200文字以内で入力してください"}), 400
    try:
        urls = analyzer.search_competitors(keyword)
        if not urls:
            return jsonify({"ok": False, "error": "検索結果が見つかりませんでした。キーワードを変えて試してください"}), 404
        return jsonify({"ok": True, "urls": urls})
    except Exception:
        logger.exception("search failed")
        return jsonify({"ok": False, "error": err("fetch_failed")}), 500


@bp.route("/analyze", methods=["POST"])
def analyze():
    keyword = request.form.get("keyword", "").strip()
    urls_raw = request.form.get("urls", "").strip()
    if not keyword:
        return jsonify({"ok": False, "error": "キーワードを入力してください"}), 400

    urls = [u.strip() for u in urls_raw.split("\n")
            if u.strip().startswith("http")][:5]
    if not urls:
        return jsonify({"ok": False, "error": "有効なURLがありません"}), 400

    try:
        pages = [analyzer.scrape_page(u) for u in urls]
        ai_report = analyzer.analyze_with_claude(keyword, pages)
        return jsonify({"ok": True, "pages": pages, "analysis": ai_report, "keyword": keyword})
    except anthropic.AuthenticationError:
        logger.exception("analyze failed: invalid API key")
        return jsonify({"ok": False, "error": err("missing_anthropic")}), 500
    except analyzer.TRANSIENT_ANTHROPIC_ERRORS:
        logger.exception("analyze failed: Claude API busy")
        return jsonify({"ok": False, "error": err("ai_busy")}), 503
    except Exception as e:
        logger.exception("analyze failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "competitor-research")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5013)
