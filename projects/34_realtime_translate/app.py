import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, Response, render_template, request

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf

load_dotenv()

BASE_DIR = Path(__file__).parent
DB_PATH = BASE_DIR / "instance" / "translate_history.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

LANGS = [("ja", "日本語"), ("en", "English"), ("zh", "中文"), ("ko", "한국어")]

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _gemini_client


def _stream_translate(text: str, lang_label: str):
    """Gemini APIのストリーミングモードで翻訳結果を逐次yieldする。"""
    from google.genai import types

    client = _get_gemini_client()
    prompt = (
        f"次のテキストを{lang_label}に翻訳してください。"
        f"翻訳結果のみを出力し、説明や引用符は付けないでください。\n\n{text}"
    )
    stream = client.models.generate_content_stream(
        model="gemini-2.5-flash",
        contents=prompt,
        config=types.GenerateContentConfig(
            max_output_tokens=1000,
            thinking_config=types.ThinkingConfig(thinking_budget=0),
        ),
    )
    for chunk in stream:
        if chunk.text:
            yield chunk.text


def _init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            original_text TEXT NOT NULL,
            ja TEXT, en TEXT, zh TEXT, ko TEXT,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    conn.close()


def _save_history(original_text: str, results: dict) -> int:
    conn = sqlite3.connect(DB_PATH)
    cur = conn.execute(
        "INSERT INTO history (original_text, ja, en, zh, ko, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (
            original_text,
            results.get("ja", ""),
            results.get("en", ""),
            results.get("zh", ""),
            results.get("ko", ""),
            datetime.now(timezone.utc).isoformat(),
        ),
    )
    conn.commit()
    record_id = cur.lastrowid
    conn.close()
    return record_id


def _load_history(limit: int = 20):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        "SELECT * FROM history ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()
    conn.close()
    return rows


def _sse_event(event: str, data: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(data, ensure_ascii=False)}\n\n"


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    # hub_appの全アプリが同じCookie名"session"を共有すると、別アプリへの訪問で
    # セッションが上書きされCSRFトークンが消える問題があるため、一意な名前にする。
    app.config["SESSION_COOKIE_NAME"] = "session_34_realtime_translate"
    init_csrf(app)
    _init_db()

    @app.route("/", methods=["GET"])
    def index():
        history = _load_history()
        return render_template("index.html", history=history, langs=LANGS)

    @app.route("/translate", methods=["POST"])
    def translate():
        payload = request.get_json(silent=True) or {}
        text = (payload.get("text") or "").strip()

        if not text:
            return Response(
                _sse_event("error", {"message": "テキストを入力してください。"}),
                mimetype="text/event-stream",
            )
        if not os.environ.get("GEMINI_API_KEY"):
            return Response(
                _sse_event("error", {"message": "GEMINI_API_KEYが設定されていません。"}),
                mimetype="text/event-stream",
            )

        def generate():
            results = {}
            for code, label in LANGS:
                yield _sse_event("start", {"lang": code})
                full_text = ""
                try:
                    for delta in _stream_translate(text, label):
                        full_text += delta
                        yield _sse_event("chunk", {"lang": code, "delta": delta})
                except Exception as e:
                    yield _sse_event("error", {"lang": code, "message": str(e)})
                results[code] = full_text
                yield _sse_event("done", {"lang": code, "text": full_text})

            record_id = _save_history(text, results)
            yield _sse_event("complete", {"id": record_id})

        return Response(generate(), mimetype="text/event-stream")

    @app.route("/portfolio")
    def portfolio():
        from flask import redirect
        return redirect("https://ai-labo.space/", code=301)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5034, threaded=True)
