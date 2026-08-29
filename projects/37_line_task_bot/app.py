import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from dotenv import load_dotenv
from flask import Flask, abort, jsonify, redirect, render_template, request, url_for
from linebot.v3 import WebhookHandler
from linebot.v3.exceptions import InvalidSignatureError
from linebot.v3.messaging import (
    ApiClient,
    Configuration,
    MessagingApi,
    PushMessageRequest,
    ReplyMessageRequest,
    TextMessage,
)
from linebot.v3.webhooks import MessageEvent, TextMessageContent

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

from models import Task, db

load_dotenv()

BASE_DIR = Path(__file__).parent
JST = pytz.timezone("Asia/Tokyo")
CATEGORIES = ["仕事", "プライベート", "買い物", "勉強", "その他"]

EXTRACT_PROMPT_TEMPLATE = (
    "次のメッセージからタスクを抽出してください。\n"
    f"カテゴリは次のいずれか一つ: {', '.join(CATEGORIES)}\n"
    "期限が明記されていない場合はnullにしてください。日付は今日を基準に解釈し、"
    "YYYY-MM-DD形式で出力してください。今日の日付: {today}\n\n"
    "メッセージ: {message}\n\n"
    '出力JSON形式: {{"task_name": "<タスク名>", "due_date": "<YYYY-MM-DD または null>", '
    '"category": "<カテゴリ名>"}}'
)

_scheduler: BackgroundScheduler | None = None
handler: WebhookHandler | None = None


def _get_handler() -> WebhookHandler:
    global handler
    if handler is None:
        handler = WebhookHandler(os.environ["LINE_CHANNEL_SECRET"])
        handler.add(MessageEvent, message=TextMessageContent)(_on_text_message)
    return handler


def _get_messaging_api() -> MessagingApi:
    configuration = Configuration(access_token=os.environ["LINE_CHANNEL_ACCESS_TOKEN"])
    api_client = ApiClient(configuration)
    return MessagingApi(api_client)


def _extract_task(message: str) -> dict:
    today = date.today().isoformat()
    try:
        result = call_claude_json(
            None, "claude-haiku-4-5-20251001", 300,
            EXTRACT_PROMPT_TEMPLATE.format(today=today, message=message),
        )
        if result.get("category") not in CATEGORIES:
            result["category"] = "その他"
        return result
    except Exception:
        return {"task_name": message[:100], "due_date": None, "category": "その他"}


def _format_task_list(user_id: str) -> str:
    tasks = Task.query.filter_by(line_user_id=user_id, status="未完了").order_by(Task.due_date).all()
    if not tasks:
        return "未完了のタスクはありません。"
    lines = [f"・{t.task_name}（期限: {t.due_date or '未設定'} / {t.category}）" for t in tasks]
    return "【未完了タスク一覧】\n" + "\n".join(lines)


def _on_text_message(event: MessageEvent) -> None:
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text == "一覧":
        reply_text = _format_task_list(user_id)
    else:
        extracted = _extract_task(text)
        task = Task(
            line_user_id=user_id,
            task_name=extracted.get("task_name", text[:100]),
            due_date=extracted.get("due_date"),
            category=extracted.get("category", "その他"),
        )
        db.session.add(task)
        db.session.commit()
        reply_text = (
            f"タスクを登録しました。\n"
            f"・タスク名: {task.task_name}\n"
            f"・期限: {task.due_date or '未設定'}\n"
            f"・カテゴリ: {task.category}"
        )

    messaging_api = _get_messaging_api()
    messaging_api.reply_message(
        ReplyMessageRequest(reply_token=event.reply_token, messages=[TextMessage(text=reply_text)])
    )


def send_due_reminders() -> int:
    """期限1日前のタスクへLINEでリマインダーを送る。送信件数を返す。"""
    tomorrow = (datetime.now(JST).date() + timedelta(days=1)).isoformat()
    tasks = Task.query.filter_by(due_date=tomorrow, status="未完了", reminder_sent=False).all()

    if not tasks:
        return 0

    messaging_api = _get_messaging_api()
    sent = 0
    for task in tasks:
        try:
            messaging_api.push_message(
                PushMessageRequest(
                    to=task.line_user_id,
                    messages=[TextMessage(text=f"【リマインダー】明日が期限のタスクがあります。\n・{task.task_name}（{task.category}）")],
                )
            )
            task.reminder_sent = True
            sent += 1
        except Exception:
            continue
    db.session.commit()
    return sent


class _ReverseProxied:
    """nginxが"/line-task-bot/"プレフィックスを剥がして転送する構成のため、
    Flask自身はそのプレフィックスの存在を知らずurl_for()が絶対パスを生成してしまい、
    static配信・リダイレクトが本番だけ壊れる問題があった。環境変数APP_URL_PREFIXで
    マウント先プレフィックスを明示し、WSGI環境のSCRIPT_NAMEキーに設定することで
    url_for()が正しいパスを生成できるようにする。
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
        forwarded_proto = environ.get("HTTP_X_FORWARDED_PROTO")
        if forwarded_proto:
            environ["wsgi.url_scheme"] = forwarded_proto
        return self.wsgi_app(environ, start_response)


def create_app(start_scheduler: bool = True):
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.wsgi_app = _ReverseProxied(app.wsgi_app, os.environ.get("APP_URL_PREFIX", ""))
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'instance' / 'tasks.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    (BASE_DIR / "instance").mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    with app.app_context():
        db.create_all()

    @app.route("/webhook", methods=["POST"])
    def webhook():
        signature = request.headers.get("X-Line-Signature", "")
        body = request.get_data(as_text=True)
        try:
            _get_handler().handle(body, signature)
        except InvalidSignatureError:
            abort(400)
        return "OK"

    @app.route("/", methods=["GET"])
    def index():
        tasks = Task.query.order_by(Task.status, Task.due_date).all()
        return render_template("index.html", tasks=tasks)

    @app.route("/tasks/<int:task_id>/complete", methods=["POST"])
    def complete_task(task_id):
        task = db.session.get(Task, task_id)
        if task is None:
            abort(404)
        task.status = "完了"
        db.session.commit()
        return redirect(url_for("index"))

    @app.route("/api/run-reminders", methods=["POST"])
    def run_reminders():
        sent = send_due_reminders()
        return jsonify({"ok": True, "sent": sent})

    @app.route("/portfolio")
    def portfolio():
        return redirect("https://ai-labo.space/", code=301)

    def _run_reminders_with_context():
        with app.app_context():
            send_due_reminders()

    global _scheduler
    if start_scheduler and _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=JST)
        _scheduler.add_job(_run_reminders_with_context, CronTrigger(hour=9, minute=0, timezone=JST))
        _scheduler.start()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5037)
