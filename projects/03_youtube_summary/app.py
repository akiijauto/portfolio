import sys
import os
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify
from youtube import fetch_video, search_videos
from summarizer import summarize

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.errors import get as err
from shared.utils import handle_ai_error

load_dotenv()

bp = Blueprint("youtube_summary", __name__, template_folder="templates", static_folder="static")

@bp.route("/")
def index():
    return render_template("youtube_summary/index.html")

@bp.route("/search", methods=["POST"])
def search_route():
    keyword = request.form.get("keyword", "").strip()
    if not keyword:
        return jsonify({"ok": False, "error": "キーワードを入力してください"}), 400
    try:
        videos = search_videos(keyword)
        return jsonify({"ok": True, "videos": videos})
    except RuntimeError:
        return jsonify({"ok": False, "error": "検索機能が未設定です（TAVILY_API_KEY）。URLを直接入力してください"}), 503
    except Exception as e:
        return jsonify({"ok": False, "error": handle_ai_error(e, "youtube-search")}), 500

@bp.route("/summarize", methods=["POST"])
def summarize_route():
    url = request.form.get("url", "").strip()
    if not url:
        return jsonify({"ok": False, "error": "URLを入力してください"}), 400
    try:
        video_id, title, transcript = fetch_video(url)
        if len(transcript) < 50:
            return jsonify({"ok": False, "error": err("no_transcript")}), 400
        result = summarize(url, title, transcript)
        result["video_id"]       = video_id
        result["title"]          = result.get("title") or title
        result["transcript_len"] = len(transcript)
        return jsonify({"ok": True, "data": result})
    except ValueError as e:
        return jsonify({"ok": False, "error": str(e)}), 400
    except Exception as e:
        return jsonify({"ok": False, "error": handle_ai_error(e, "youtube-summary")}), 500

def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app

app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5003)
