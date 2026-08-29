import json
import os
import sys
import time
from datetime import date
from pathlib import Path

import yfinance as yf
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for
from flask_socketio import SocketIO

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import call_claude_text

load_dotenv()

BASE_DIR = Path(__file__).parent
DAILY_COMMENT_PATH = BASE_DIR / "instance" / "daily_comment.json"
DAILY_COMMENT_PATH.parent.mkdir(parents=True, exist_ok=True)

TICKERS = {
    "usdjpy": "JPY=X",
    "eurjpy": "EURJPY=X",
    "nikkei225": "^N225",
    "sp500": "^GSPC",
}

UPDATE_INTERVAL_SECONDS = 5

socketio = SocketIO(cors_allowed_origins="*", async_mode="threading")

# シングルユーザー向けの簡易アラート設定。複数ユーザー対応が必要になった場合は
# セッションやDBへの保存に変更する。
alert_state = {"usdjpy_threshold": None}


def _fetch_market_data() -> dict:
    data = {}
    for key, symbol in TICKERS.items():
        try:
            price = yf.Ticker(symbol).fast_info.get("lastPrice")
            data[key] = round(price, 3) if price is not None else None
        except Exception:
            data[key] = None
    return data


def _check_alert(data: dict) -> dict | None:
    threshold = alert_state.get("usdjpy_threshold")
    usdjpy = data.get("usdjpy")
    if threshold is not None and usdjpy is not None and usdjpy >= threshold:
        return {"pair": "USD/JPY", "rate": usdjpy, "threshold": threshold}
    return None


def _market_update_loop():
    while True:
        data = _fetch_market_data()
        socketio.emit("market_update", data)

        alert = _check_alert(data)
        if alert:
            socketio.emit("rate_alert", alert)

        time.sleep(UPDATE_INTERVAL_SECONDS)


def _get_daily_comment() -> str:
    today = date.today().isoformat()
    if DAILY_COMMENT_PATH.exists():
        try:
            cached = json.loads(DAILY_COMMENT_PATH.read_text(encoding="utf-8"))
            if cached.get("date") == today:
                return cached.get("comment", "")
        except (json.JSONDecodeError, OSError):
            pass

    comment = ""
    if os.environ.get("GEMINI_API_KEY"):
        try:
            comment = call_claude_text(
                None, "claude-haiku-4-5-20251001", 200,
                "今日の為替・株式市場についての一言コメントを日本語で1〜2文書いてください。"
                "具体的な売買判断や数値予測はせず、一般的な相場の見方として述べてください。",
            ).strip()
        except Exception:
            comment = ""

    DAILY_COMMENT_PATH.write_text(
        json.dumps({"date": today, "comment": comment}, ensure_ascii=False), encoding="utf-8"
    )
    return comment


class _ReverseProxied:
    """nginxが"/realtime-market/"プレフィックスを剥がして転送する構成のため、
    Flask自身はそのプレフィックスの存在を知らずurl_for()が絶対パスを生成してしまう問題の
    根本対応。32_gcal_summary_bot・37_line_task_botと同じ方式(WSGI標準のSCRIPT_NAME機構)。
    環境変数名は"SCRIPT_NAME"そのものにしない。gunicornがプロセス起動時にos.environ
    ["SCRIPT_NAME"]を読み取りリクエストパスとの整合性チェックを行うため、nginx側で
    プレフィックスを剥がして転送する構成とは衝突し500エラーになる。
    """

    def __init__(self, wsgi_app, script_name: str):
        self.wsgi_app = wsgi_app
        self.script_name = script_name

    def __call__(self, environ, start_response):
        if self.script_name:
            environ["SCRIPT_NAME"] = self.script_name
        forwarded_proto = environ.get("HTTP_X_FORWARDED_PROTO")
        if forwarded_proto:
            environ["wsgi.url_scheme"] = forwarded_proto
        return self.wsgi_app(environ, start_response)


def create_app(start_background: bool = True):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.wsgi_app = _ReverseProxied(app.wsgi_app, os.environ.get("APP_URL_PREFIX", ""))
    init_csrf(app)
    socketio.init_app(app)

    @app.route("/", methods=["GET"])
    def index():
        return render_template(
            "index.html",
            daily_comment=_get_daily_comment(),
            alert_threshold=alert_state.get("usdjpy_threshold"),
        )

    @app.route("/alert", methods=["POST"])
    def set_alert():
        raw = request.form.get("usdjpy_threshold", "").strip()
        if not raw:
            alert_state["usdjpy_threshold"] = None
            flash("アラート設定を解除しました。", "success")
        else:
            try:
                alert_state["usdjpy_threshold"] = float(raw)
                flash(f"USD/JPYが{raw}円を超えたら通知します。", "success")
            except ValueError:
                flash("数値を入力してください。", "error")
        return redirect(url_for("index"))

    @app.route("/portfolio")
    def portfolio():
        return redirect("https://ai-labo.space/", code=301)

    if start_background:
        socketio.start_background_task(_market_update_loop)

    return app


app = create_app()

if __name__ == "__main__":
    socketio.run(app, port=5030, debug=False)
