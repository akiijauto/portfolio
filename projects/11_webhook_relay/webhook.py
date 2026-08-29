"""GitHub Webhook の署名検証・イベントルーティング・Discord Embed 送信。"""
import hashlib
import hmac
import os
import threading
from datetime import datetime

import pytz
import requests

JST = pytz.timezone("Asia/Tokyo")
_logs: list = []
_lock = threading.Lock()
MAX_LOGS = 50


def _add_log(event: str, status: str, summary: str, preview: str = ""):
    entry = {
        "at": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        "event": event,
        "status": status,
        "summary": summary,
        "preview": preview[:300],
    }
    with _lock:
        _logs.insert(0, entry)
        if len(_logs) > MAX_LOGS:
            _logs.pop()


def get_logs() -> list:
    with _lock:
        return list(_logs)


def verify_signature(payload_bytes: bytes, signature_header: str) -> bool:
    """X-Hub-Signature-256 ヘッダーをHMAC-SHA256で検証する。"""
    secret = os.environ.get("GITHUB_WEBHOOK_SECRET", "")
    if not secret:
        return False  # シークレット未設定時は拒否（本番環境では必ず設定すること）
    if not signature_header or not signature_header.startswith("sha256="):
        return False
    expected = "sha256=" + hmac.new(
        secret.encode(), payload_bytes, hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature_header)


def _send_discord_embed(embed: dict) -> bool:
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not url:
        return False
    try:
        r = requests.post(url, json={"embeds": [embed]}, timeout=10)
        r.raise_for_status()
        return True
    except requests.RequestException:
        return False


def _build_push_embed(payload: dict) -> dict:
    repo = payload.get("repository", {}).get("full_name", "unknown")
    ref = payload.get("ref", "").replace("refs/heads/", "")
    commits = payload.get("commits", [])
    count = len(commits)
    latest_msg = commits[0].get("message", "").split("\n")[0] if commits else "(no commit)"
    pusher = payload.get("pusher", {}).get("name", "unknown")
    compare_url = payload.get("compare", "")
    return {
        "title": f"📦 Push — {repo}",
        "description": f"**{pusher}** が `{ref}` に {count} コミットをプッシュ\n> {latest_msg}",
        "url": compare_url,
        "color": 0x3B82F6,
        "footer": {"text": repo},
    }


def _build_pr_embed(payload: dict) -> dict:
    pr = payload.get("pull_request", {})
    action = payload.get("action", "")
    repo = payload.get("repository", {}).get("full_name", "unknown")
    number = pr.get("number", "?")
    title = pr.get("title", "")
    url = pr.get("html_url", "")
    user = pr.get("user", {}).get("login", "unknown")
    merged = pr.get("merged", False)

    if action == "closed" and merged:
        label = "🎉 PR マージ"
        color = 0x8B5CF6
    elif action == "opened":
        label = "🔀 PR オープン"
        color = 0x22C55E
    elif action == "closed":
        label = "❌ PR クローズ"
        color = 0xEF4444
    else:
        label = f"🔀 PR {action}"
        color = 0x94A3B8

    return {
        "title": f"{label} #{number} — {repo}",
        "description": f"**{title}**\nby {user}",
        "url": url,
        "color": color,
        "footer": {"text": repo},
    }


def _build_issue_embed(payload: dict) -> dict:
    issue = payload.get("issue", {})
    action = payload.get("action", "")
    repo = payload.get("repository", {}).get("full_name", "unknown")
    number = issue.get("number", "?")
    title = issue.get("title", "")
    url = issue.get("html_url", "")
    user = issue.get("user", {}).get("login", "unknown")

    icons = {"opened": "🐛", "closed": "✅", "reopened": "🔄"}
    icon = icons.get(action, "📋")
    colors = {"opened": 0xF97316, "closed": 0x22C55E, "reopened": 0xFBBF24}
    color = colors.get(action, 0x94A3B8)

    return {
        "title": f"{icon} Issue {action} #{number} — {repo}",
        "description": f"**{title}**\nby {user}",
        "url": url,
        "color": color,
        "footer": {"text": repo},
    }


def handle_event(event_type: str, payload: dict) -> tuple[int, str]:
    """
    イベントを処理し、(HTTPステータス, メッセージ) を返す。
    """
    if event_type == "ping":
        zen = payload.get("zen", "pong")
        _add_log("ping", "ok", zen)
        return 200, "pong"

    if event_type == "push":
        repo = payload.get("repository", {}).get("full_name", "?")
        ref = payload.get("ref", "").replace("refs/heads/", "")
        count = len(payload.get("commits", []))
        summary = f"{repo}:{ref} +{count}commits"
        embed = _build_push_embed(payload)
        ok = _send_discord_embed(embed)
        _add_log("push", "ok" if ok else "discord_err", summary)
        return 200, "ok"

    if event_type == "pull_request":
        pr = payload.get("pull_request", {})
        repo = payload.get("repository", {}).get("full_name", "?")
        action = payload.get("action", "")
        summary = f"#{pr.get('number')} {action} — {repo}"
        embed = _build_pr_embed(payload)
        ok = _send_discord_embed(embed)
        _add_log("pull_request", "ok" if ok else "discord_err", summary)
        return 200, "ok"

    if event_type == "issues":
        issue = payload.get("issue", {})
        repo = payload.get("repository", {}).get("full_name", "?")
        action = payload.get("action", "")
        summary = f"#{issue.get('number')} {action} — {repo}"
        embed = _build_issue_embed(payload)
        ok = _send_discord_embed(embed)
        _add_log("issues", "ok" if ok else "discord_err", summary)
        return 200, "ok"

    # 未対応イベント
    _add_log(event_type, "ignored", f"未対応イベント: {event_type}")
    return 200, "ignored"
