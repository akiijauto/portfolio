import sys
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify

import generator
from jgrants_api import search_subsidies, get_subsidy_detail, JGrantsError, PREFECTURES

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.errors import get as err
from shared.utils import handle_ai_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
bp = Blueprint("subsidy_matching", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template("subsidy_matching/index.html", prefectures=PREFECTURES)


@bp.route("/api/search", methods=["POST"])
def api_search():
    keyword = request.form.get("keyword", "").strip()
    prefecture = request.form.get("prefecture", "").strip()
    only_open = request.form.get("only_open", "1") == "1"

    if len(keyword) < 2:
        return jsonify({"ok": False, "error": "キーワードは2文字以上で入力してください"}), 400
    if len(keyword) > 100:
        return jsonify({"ok": False, "error": "100文字以内で入力してください"}), 400

    try:
        results = search_subsidies(keyword, prefecture, only_open)
        return jsonify({"ok": True, "results": results})
    except JGrantsError:
        return jsonify({"ok": False, "error": err("fetch_failed")}), 502


@bp.route("/api/match", methods=["POST"])
def api_match():
    subsidy_id = request.form.get("subsidy_id", "").strip()
    business_desc = request.form.get("business_desc", "").strip()

    if not subsidy_id:
        return jsonify({"ok": False, "error": "補助金を選択してください"}), 400
    if not business_desc:
        return jsonify({"ok": False, "error": "事業内容を入力してください"}), 400
    if len(business_desc) > 1500:
        return jsonify({"ok": False, "error": "事業内容は1500文字以内で入力してください"}), 400

    try:
        subsidy = get_subsidy_detail(subsidy_id)
    except JGrantsError:
        return jsonify({"ok": False, "error": err("fetch_failed")}), 502

    try:
        result = generator.match_subsidy(business_desc, subsidy)
        return jsonify({"ok": True, "subsidy": subsidy, "match": result})
    except Exception as e:
        logger.exception("subsidy matching failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "subsidy-matching")}), 500


@bp.route("/api/plan", methods=["POST"])
def api_plan():
    subsidy_id = request.form.get("subsidy_id", "").strip()
    business_desc = request.form.get("business_desc", "").strip()
    focus_points = request.form.get("focus_points", "").strip()

    if not subsidy_id:
        return jsonify({"ok": False, "error": "補助金を選択してください"}), 400
    if not business_desc:
        return jsonify({"ok": False, "error": "事業内容を入力してください"}), 400
    if len(business_desc) > 1500:
        return jsonify({"ok": False, "error": "事業内容は1500文字以内で入力してください"}), 400
    if len(focus_points) > 500:
        return jsonify({"ok": False, "error": "重視したい点は500文字以内で入力してください"}), 400

    try:
        subsidy = get_subsidy_detail(subsidy_id)
    except JGrantsError:
        return jsonify({"ok": False, "error": err("fetch_failed")}), 502

    try:
        plan = generator.generate_business_plan(business_desc, subsidy, focus_points)
        return jsonify({"ok": True, "subsidy": subsidy, "plan": plan})
    except Exception as e:
        logger.exception("business plan generation failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "subsidy-matching")}), 500


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5018)
