import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify
from scraper import fetch_article, search_articles
from summarizer import summarize

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.errors import get as err
from shared.utils import handle_ai_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

bp = Blueprint("web_article_summary", __name__, template_folder="templates", static_folder="static")

@bp.route("/")
def index():
    return render_template("web_article_summary/index.html")

@bp.route("/search", methods=["POST"])
def search_route():
    keyword = request.form.get("keyword", "").strip()
    if not keyword:
        return jsonify({"ok": False, "error": "検索キーワードを入力してください"}), 400
    if len(keyword) > 200:
        return jsonify({"ok": False, "error": "200文字以内で入力してください"}), 400
    try:
        results = search_articles(keyword)
    except RuntimeError:
        return jsonify({"ok": False, "error": "検索機能が未設定です（TAVILY_API_KEY）。URLを直接入力してください"}), 503
    except Exception:
        logger.exception("search failed")
        return jsonify({"ok": False, "error": err("fetch_failed")}), 500
    if not results:
        return jsonify({"ok": False, "error": "検索結果が見つかりませんでした。キーワードを変えて試してください"}), 404
    return jsonify({"ok": True, "results": results})

@bp.route("/summarize", methods=["POST"])
def summarize_route():
    url = request.form.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URLを入力してください"}), 400
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        text, title = fetch_article(url)
    except Exception:
        logger.exception("fetch_article failed")
        return jsonify({"ok": False, "error": err("fetch_failed")}), 500
    if len(text) < 100:
        return jsonify({"ok": False, "error": err("js_site")}), 400
    try:
        result = summarize(url, text, title)
    except Exception as e:
        logger.exception("summarize failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "web-article-summary")}), 500
    result["url"]      = url
    result["char_len"] = len(text)
    return jsonify({"ok": True, "data": result})

def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5002)
