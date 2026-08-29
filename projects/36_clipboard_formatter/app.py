import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request
from flask_cors import CORS

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_text

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "instance" / "history.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

MODE_PROMPTS = {
    "summarize": "次のテキストを2〜3文に要約してください。",
    "bullet": "次のテキストを要点ごとの箇条書きに変換してください。",
    "proofread": "次のテキストの誤字脱字を修正し、自然な文章に整えてください。",
    "polite": "次のテキストを丁寧語（敬語）の文章に変換してください。",
}
MODE_LABELS = {
    "summarize": "要約",
    "bullet": "箇条書き変換",
    "proofread": "誤字修正",
    "polite": "丁寧語変換",
}


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            mode TEXT NOT NULL,
            original_text TEXT NOT NULL,
            result_text TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _save_history(mode: str, original_text: str, result_text: str) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO history (mode, original_text, result_text, created_at) VALUES (?, ?, ?, ?)",
        (mode, original_text, result_text, datetime.now(timezone.utc).isoformat()),
    )
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id


def _load_history(limit: int = 30):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def _format_text(mode: str, text: str) -> str:
    instruction = MODE_PROMPTS.get(mode, MODE_PROMPTS["proofread"])
    prompt = f"{instruction}\n出力は整形後のテキストのみとし、説明や前置きは付けないでください。\n\n{text}"
    return call_claude_text(None, "claude-haiku-4-5-20251001", 1000, prompt).strip()


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    # Chrome拡張（chrome-extension://<拡張ID>）からのリクエストを許可する。
    # 拡張IDはインストール環境ごとに変わるため、このAPIは認証なしの
    # 整形専用エンドポイントとしてオープンに許可している。
    CORS(app, resources={r"/api/*": {"origins": "*"}})
    _init_db()

    @app.route("/", methods=["GET"])
    def index():
        history = _load_history()
        return render_template("index.html", history=history, mode_labels=MODE_LABELS)

    @app.route("/api/format", methods=["POST"])
    def api_format():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()
        mode = payload.get("mode") or "proofread"

        if not text:
            return jsonify({"ok": False, "error": "テキストを入力してください。"}), 400
        if len(text) > 5000:
            return jsonify({"ok": False, "error": "テキストは5000文字以内にしてください。"}), 400
        if mode not in MODE_PROMPTS:
            return jsonify({"ok": False, "error": "未対応の整形モードです。"}), 400

        try:
            result_text = _format_text(mode, text)
        except Exception:
            return jsonify({"ok": False, "error": "AIによる整形に失敗しました。"}), 502

        _save_history(mode, text, result_text)
        return jsonify({"ok": True, "result": result_text})

    @app.route("/api/history", methods=["GET"])
    def api_history():
        history = _load_history()
        return jsonify({
            "ok": True,
            "history": [
                {
                    "id": row["id"],
                    "mode": row["mode"],
                    "original_text": row["original_text"],
                    "result_text": row["result_text"],
                    "created_at": row["created_at"],
                }
                for row in history
            ],
        })

    @app.route("/portfolio")
    def portfolio():
        from flask import redirect
        return redirect("https://ai-labo.space/", code=301)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5036)
