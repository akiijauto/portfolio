import os
import re
import smtplib
import sys
from datetime import datetime, timezone
from email.mime.text import MIMEText
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, flash, redirect, render_template, request, url_for

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.utils import call_claude_json

load_dotenv()

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
CATEGORIES = ["新規お問い合わせ", "サポート依頼", "申込み", "クレーム", "その他"]

CLASSIFY_PROMPT_TEMPLATE = (
    "次のお問い合わせ内容を要約し、カテゴリを分類してください。\n"
    f"カテゴリは次のいずれか一つを選んでください: {', '.join(CATEGORIES)}\n\n"
    "用件: {subject}\n詳細: {detail}\n\n"
    '出力JSON形式: {{"category": "<カテゴリ名>", "summary": "<2〜3文の日本語要約>"}}'
)


def _get_notion_client():
    from notion_client import Client
    return Client(auth=os.environ["NOTION_API_KEY"])


def _classify_inquiry(subject: str, detail: str) -> dict:
    try:
        result = call_claude_json(
            None, "claude-haiku-4-5-20251001", 300,
            CLASSIFY_PROMPT_TEMPLATE.format(subject=subject, detail=detail),
        )
        if result.get("category") not in CATEGORIES:
            result["category"] = "その他"
        return result
    except Exception:
        return {"category": "その他", "summary": detail[:200]}


def _save_to_notion(name: str, email: str, subject: str, category: str, summary: str) -> str:
    notion = _get_notion_client()
    page = notion.pages.create(
        parent={"database_id": os.environ["NOTION_DATABASE_ID"]},
        properties={
            "名前": {"title": [{"text": {"content": name}}]},
            "メール": {"email": email},
            "用件": {"rich_text": [{"text": {"content": subject}}]},
            "カテゴリ": {"select": {"name": category}},
            "要約": {"rich_text": [{"text": {"content": summary}}]},
            "ステータス": {"select": {"name": "新規"}},
            "日時": {"date": {"start": datetime.now(timezone.utc).isoformat()}},
        },
    )
    return page["id"]


def _send_email(to_addr: str, subject: str, body: str) -> None:
    smtp_host = os.environ.get("SMTP_HOST")
    if not smtp_host:
        return

    msg = MIMEText(body)
    msg["Subject"] = subject
    msg["From"] = os.environ.get("SMTP_USER", "")
    msg["To"] = to_addr

    with smtplib.SMTP(smtp_host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as server:
        server.starttls()
        smtp_user = os.environ.get("SMTP_USER")
        smtp_pass = os.environ.get("SMTP_PASS")
        if smtp_user and smtp_pass:
            server.login(smtp_user, smtp_pass)
        server.send_message(msg)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    # hub_appの全アプリが同じCookie名"session"を共有すると、別アプリへの訪問で
    # セッションが上書きされCSRFトークンが消える問題があるため、一意な名前にする。
    app.config["SESSION_COOKIE_NAME"] = "session_29_form_notion_bot"
    init_csrf(app)

    @app.route("/", methods=["GET"])
    def index():
        return render_template("index.html")

    @app.route("/submit", methods=["POST"])
    def submit():
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip()
        subject = request.form.get("subject", "").strip()
        detail = request.form.get("detail", "").strip()

        if not name or len(name) > 50:
            flash("お名前を入力してください（50文字以内）。", "error")
            return redirect(url_for("index"))
        if not email or len(email) > 100 or not EMAIL_RE.match(email):
            flash("メールアドレスの形式を確認してください。", "error")
            return redirect(url_for("index"))
        if not subject or len(subject) > 100:
            flash("用件を入力してください（100文字以内）。", "error")
            return redirect(url_for("index"))
        if not detail or len(detail) > 2000:
            flash("詳細を入力してください（2000文字以内）。", "error")
            return redirect(url_for("index"))

        classification = _classify_inquiry(subject, detail)
        category = classification.get("category", "その他")
        summary = classification.get("summary", "")

        try:
            _save_to_notion(name, email, subject, category, summary)
        except Exception:
            flash("送信に失敗しました。時間をおいて再度お試しください。", "error")
            return redirect(url_for("index"))

        admin_email = os.environ.get("ADMIN_EMAIL")
        if admin_email:
            try:
                _send_email(
                    admin_email,
                    f"【新規お問い合わせ】{subject}",
                    f"名前: {name}\nメール: {email}\nカテゴリ: {category}\n要約: {summary}\n\n詳細:\n{detail}",
                )
            except Exception:
                pass

        try:
            _send_email(
                email,
                "お問い合わせありがとうございます",
                f"{name}様\n\nお問い合わせいただきありがとうございます。"
                f"内容を確認のうえ、担当者よりご連絡いたします。\n\n"
                f"【お問い合わせ内容】\n{subject}\n{detail}",
            )
        except Exception:
            pass

        flash("お問い合わせを受け付けました。ご回答までお待ちください。", "success")
        return redirect(url_for("index"))

    @app.route("/portfolio")
    def portfolio():
        return redirect("https://ai-labo.space/", code=301)

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5029)
