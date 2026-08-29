import json
import os
import smtplib
import sys
from datetime import datetime, timedelta, timezone
from email.mime.text import MIMEText
from pathlib import Path

import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, session, url_for
from google.auth.transport.requests import Request as GoogleAuthRequest
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import call_claude_text

load_dotenv()

BASE_DIR = Path(__file__).parent
TOKEN_PATH = BASE_DIR / "instance" / "google_token.json"
TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)

SCOPES = ["https://www.googleapis.com/auth/calendar.readonly"]
JST = pytz.timezone("Asia/Tokyo")

_scheduler: BackgroundScheduler | None = None


def _build_oauth_flow(redirect_uri: str, code_verifier: str | None = None) -> Flow:
    client_config = {
        "web": {
            "client_id": os.environ["GOOGLE_CLIENT_ID"],
            "client_secret": os.environ["GOOGLE_CLIENT_SECRET"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [redirect_uri],
        }
    }
    return Flow.from_client_config(
        client_config, scopes=SCOPES, redirect_uri=redirect_uri, code_verifier=code_verifier
    )


def _load_credentials() -> Credentials | None:
    if not TOKEN_PATH.exists():
        return None
    data = json.loads(TOKEN_PATH.read_text(encoding="utf-8"))
    creds = Credentials.from_authorized_user_info(data, SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(GoogleAuthRequest())
        _save_credentials(creds)
    return creds


def _save_credentials(creds: Credentials) -> None:
    TOKEN_PATH.write_text(creds.to_json(), encoding="utf-8")


def _fetch_week_events(creds: Credentials) -> list[dict]:
    service = build("calendar", "v3", credentials=creds)
    now = datetime.now(timezone.utc)
    time_min = now.isoformat()
    time_max = (now + timedelta(days=7)).isoformat()

    result = service.events().list(
        calendarId="primary",
        timeMin=time_min,
        timeMax=time_max,
        singleEvents=True,
        orderBy="startTime",
        maxResults=50,
    ).execute()

    events = []
    for item in result.get("items", []):
        start = item.get("start", {}).get("dateTime") or item.get("start", {}).get("date")
        events.append({"summary": item.get("summary", "（無題の予定）"), "start": start})
    return events


def _summarize_events(events: list[dict]) -> str:
    if not events:
        return "今週は登録されている予定がありません。"

    events_text = "\n".join(f"- {e['start']}: {e['summary']}" for e in events)
    prompt = (
        "次は今週のGoogleカレンダーの予定一覧です。重要度の高い予定から並べ替え、"
        "日本語で簡潔に要約してください（3〜5行程度）。\n\n" + events_text
    )
    try:
        return call_claude_text(None, "claude-haiku-4-5-20251001", 500, prompt).strip()
    except Exception:
        return "AIによる要約に失敗しました。予定一覧は以下の通りです。\n" + events_text


def _send_discord(message: str) -> None:
    webhook_url = os.environ.get("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    requests.post(webhook_url, json={"content": message}, timeout=10)


def _send_email(subject: str, body: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    if not smtp_host or not smtp_user:
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = smtp_user
    msg["To"] = smtp_user

    with smtplib.SMTP(smtp_host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as server:
        server.starttls()
        smtp_pass = os.environ.get("SMTP_PASS")
        if smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def send_daily_summary() -> str:
    """今週の予定を取得し、AI要約をDiscord・メールへ送信する。戻り値は要約テキスト。"""
    creds = _load_credentials()
    if creds is None:
        return ""

    events = _fetch_week_events(creds)
    summary = _summarize_events(events)

    today = datetime.now(JST).strftime("%Y-%m-%d")
    message = f"【{today} 今週の予定まとめ】\n{summary}"

    try:
        _send_discord(message)
    except Exception:
        pass
    try:
        _send_email(f"今週の予定まとめ（{today}）", message)
    except Exception:
        pass

    return summary


class _ReverseProxied:
    """nginxが"/gcal-summary-bot/"プレフィックスを剥がして転送する構成のため、
    Flask自身はそのプレフィックスの存在を知らずurl_for()が絶対パスを生成してしまい、
    static配信・リダイレクト・OAuthのredirect_uriなどが本番だけ壊れる問題があった。
    環境変数APP_URL_PREFIXでマウント先プレフィックスを明示し、WSGI環境のSCRIPT_NAME
    キーに設定することでurl_for()が正しいプレフィックス付きパスを生成できるようにする。
    (環境変数名は"SCRIPT_NAME"そのものにしない。gunicornはos.environ["SCRIPT_NAME"]を
    プロセス起動時に読み取り、自前でリクエストパスとの整合性チェックを行うため、
    nginx側でプレフィックスを剥がして転送する今回の構成とは衝突し500エラーになる。)
    """

    def __init__(self, wsgi_app, script_name: str):
        self.wsgi_app = wsgi_app
        self.script_name = script_name

    def __call__(self, environ, start_response):
        if self.script_name:
            environ["SCRIPT_NAME"] = self.script_name
        # nginxはSSLを終端し、バックエンドへは平文HTTPで転送するため、
        # X-Forwarded-Protoヘッダーが無いとFlaskは「HTTP接続」だと誤認し、
        # url_for(_external=True)がhttps://ではなくhttp://を生成してしまう
        # (Google OAuthのredirect_uri不一致エラーの原因になる)。
        forwarded_proto = environ.get("HTTP_X_FORWARDED_PROTO")
        if forwarded_proto:
            environ["wsgi.url_scheme"] = forwarded_proto
        return self.wsgi_app(environ, start_response)


def create_app(start_scheduler: bool = True):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.wsgi_app = _ReverseProxied(app.wsgi_app, os.environ.get("APP_URL_PREFIX", ""))
    init_csrf(app)

    @app.route("/", methods=["GET"])
    def index():
        creds = _load_credentials()
        events = []
        summary = ""
        if creds is not None:
            try:
                events = _fetch_week_events(creds)
                summary = _summarize_events(events)
            except Exception:
                flash("Googleカレンダーからの予定取得に失敗しました。再認証してください。", "error")
        return render_template("index.html", authenticated=creds is not None, events=events, summary=summary)

    @app.route("/auth/login", methods=["GET"])
    def auth_login():
        flow = _build_oauth_flow(url_for("auth_callback", _external=True))
        auth_url, _ = flow.authorization_url(access_type="offline", prompt="consent")
        # PKCEのcode_verifierはFlowインスタンス内にしか保持されないため、
        # callbackで新規Flowを作ると検証用の値が失われ"Missing code verifier"になる。
        # セッションに保存し、callback側で同じ値を使ってFlowを再構築する。
        session["oauth_code_verifier"] = flow.code_verifier
        return redirect(auth_url)

    @app.route("/auth/callback", methods=["GET"])
    def auth_callback():
        code_verifier = session.pop("oauth_code_verifier", None)
        flow = _build_oauth_flow(url_for("auth_callback", _external=True), code_verifier=code_verifier)
        flow.fetch_token(code=request.args.get("code"))
        _save_credentials(flow.credentials)
        flash("Googleカレンダーと連携しました。", "success")
        return redirect(url_for("index"))

    @app.route("/run-now", methods=["POST"])
    def run_now():
        summary = send_daily_summary()
        if summary:
            flash("今週の予定まとめを送信しました。", "success")
        else:
            flash("Googleカレンダーと未連携のため、送信できませんでした。", "error")
        return redirect(url_for("index"))

    @app.route("/portfolio")
    def portfolio():
        return redirect("https://ai-labo.space/", code=301)

    global _scheduler
    if start_scheduler and _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=JST)
        _scheduler.add_job(send_daily_summary, CronTrigger(hour=8, minute=0, timezone=JST))
        _scheduler.start()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5032)
