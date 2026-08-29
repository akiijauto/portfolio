"""管理者への通知（メール / Discord）。

いずれも未設定の場合はログ出力のみに留め、例外は呼び出し元に伝播させない
（通知失敗がユーザー向けレスポンスに影響しないようにする）。
"""
import os
import logging
import smtplib
from email.mime.text import MIMEText

import requests

logger = logging.getLogger(__name__)

ADMIN_EMAIL = os.environ.get("ADMIN_EMAIL", "admin@example.com")


def _webhook_error(status: int) -> str:
    """DiscordのHTTPステータスを原因の分かる文言にする。戻り値にURLは含めない。"""
    if status == 404:
        return "HTTP 404: Webhookが削除されています。Discordで再発行し.envを更新してください"
    if status in (401, 403):
        return f"HTTP {status}: Webhook URLが不正か、送信が拒否されました"
    if status == 429:
        return "HTTP 429: レート制限に達しました"
    return f"HTTP {status}: 送信に失敗しました"


def _mask(text: str, webhook: str) -> str:
    """例外メッセージに混入したWebhook URLを伏せる（ログに平文で残さないため）。"""
    return text.replace(webhook, "<DISCORD_WEBHOOK_URL>")


def notify_admin(subject: str, body: str) -> None:
    """管理者へ通知する。SMTP設定があればメール、DISCORD_WEBHOOK_URLがあればDiscordにも送信する。"""
    sent = False

    smtp_host = os.environ.get("SMTP_HOST")
    smtp_user = os.environ.get("SMTP_USER")
    smtp_password = os.environ.get("SMTP_PASSWORD")

    if smtp_host and smtp_user and not smtp_password:
        # ログインせずに送るとGmailは 530 Authentication Required で必ず拒否する。
        # 10秒のタイムアウトを待って例外になるだけなので、送らずに理由を残す。
        logger.error(
            "SMTP_PASSWORD が未設定のためメール通知を送りません"
            "（Gmailは通常のログインパスワードではなくアプリパスワードが必要）"
        )
    elif smtp_host:
        try:
            msg = MIMEText(body)
            msg["Subject"] = subject
            msg["From"] = smtp_user or ADMIN_EMAIL
            msg["To"] = ADMIN_EMAIL
            with smtplib.SMTP(smtp_host, int(os.environ.get("SMTP_PORT", "587")), timeout=10) as server:
                server.starttls()
                if smtp_user and smtp_password:
                    server.login(smtp_user, smtp_password)
                server.send_message(msg)
            sent = True
        except Exception:
            logger.exception("管理者へのメール通知に失敗しました")

    # 管理者通知はクレジット切れなどの障害系なので #errors 側を優先する。
    webhook = os.environ.get("DISCORD_WEBHOOK_ERRORS") or os.environ.get(
        "DISCORD_WEBHOOK_URL"
    )
    if webhook:
        try:
            res = requests.post(webhook, json={"content": f"**{subject}**\n{body}"}, timeout=10)
            # 戻り値を捨てるとWebhook失効(404)を検知できない。さらにsent=Trueが立つため
            # 「通知先が未設定」の警告すら出ず、完全に無言で止まる。
            if res.status_code >= 400:
                logger.error("管理者へのDiscord通知に失敗しました: %s", _webhook_error(res.status_code))
            else:
                sent = True
        except Exception as e:
            logger.error("管理者へのDiscord通知に失敗しました: %s", _mask(str(e), webhook))

    if not sent:
        logger.warning("管理者通知先が未設定のため通知できませんでした: %s / %s", subject, body)
