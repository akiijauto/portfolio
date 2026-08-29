"""
操作ログを OPERATION_LOG.md・Notion・Discord の3か所に記録するユーティリティ。

使い方（インポート）:
    from logger import log_operation, notify_work
    log_operation("git push", "GitHub main ブランチへプッシュ", category="git操作")
    notify_work("全12項目の品質改善・GitHubプッシュ完了")

使い方（CLI）:
    python logger.py "git push" "GitHub main ブランチへプッシュ" "git操作"
    python logger.py --notify "作業内容50文字以内"
"""
import os
import sys
import json
import requests as http_req
from datetime import datetime, timezone, timedelta
from pathlib import Path

JST = timezone(timedelta(hours=9))
from dotenv import load_dotenv
from notion_client import Client

load_dotenv()

ROOT        = Path(__file__).resolve().parent
LOG_FILE    = ROOT / "OPERATION_LOG.md"
CONFIG_FILE = ROOT / "config.local.json"

notion = Client(auth=os.environ["NOTION_TOKEN"])

# ── 設定ファイル管理 ────────────────────────────────────────────────
def _load_config() -> dict:
    if CONFIG_FILE.exists():
        return json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
    return {}

def _save_config(data: dict):
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

# ── Notion ログDB の取得または作成 ───────────────────────────────────
def _get_or_create_log_db() -> str:
    config = _load_config()
    db_id  = config.get("notion_log_db_id", "")
    if db_id:
        return db_id

    portfolio_id = os.environ.get("NOTION_PORTFOLIO_PAGE_ID", "")
    if not portfolio_id:
        raise ValueError("NOTION_PORTFOLIO_PAGE_ID が .env に未設定です")

    db = notion.databases.create(
        parent={"type": "page_id", "page_id": portfolio_id},
        title=[{"type": "text", "text": {"content": "操作ログ"}}],
        properties={
            "操作名":    {"title": {}},
            "内容":     {"rich_text": {}},
            "カテゴリ": {"select": {"options": [
                {"name": "git操作",     "color": "blue"},
                {"name": ".gitignore",  "color": "yellow"},
                {"name": "API呼び出し", "color": "green"},
                {"name": ".env操作",    "color": "red"},
                {"name": "外部送信",    "color": "orange"},
                {"name": "その他",      "color": "gray"},
            ]}},
            "承認": {"checkbox": {}},
            "日時": {"date": {}},
        }
    )
    config["notion_log_db_id"] = db["id"]
    _save_config(config)
    print(f"Notion 操作ログDB を作成しました (ID: {db['id']})")
    return db["id"]

# ── Discord 作業通知 ─────────────────────────────────────────────────
def notify_work(summary: str):
    """作業内容をDiscordに通知する（50文字以内）。

    Claudeが作業を完了した際に呼び出す。
    summary: 作業内容の要約（50文字以内）
    """
    if len(summary) > 50:
        summary = summary[:47] + "..."
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook:
        print("[通知スキップ] DISCORD_WEBHOOK_URL 未設定")
        return
    now = datetime.now(JST).strftime("%m/%d %H:%M")
    try:
        http_req.post(webhook, json={"content": f"🤖 `{now}` {summary}"}, timeout=10)
        print(f"[Discord通知] {summary}")
    except Exception as e:
        print(f"[Discord通知失敗] {e}")

# ── メイン関数 ──────────────────────────────────────────────────────
def log_operation(operation: str, detail: str,
                  approved: bool = True, category: str = "その他"):
    """OPERATION_LOG.md と Notion の両方に操作を記録する。"""
    now     = datetime.now(JST)
    now_str = now.strftime("%Y-%m-%d %H:%M")
    status  = "✅ 承認済み" if approved else "⚠️ 事後報告"

    _write_to_file(now_str, operation, detail, status)
    _write_to_notion(now, operation, detail, approved, category)
    print(f"[ログ記録] {now_str} | {operation} | {category}")

def _write_to_file(now_str: str, operation: str, detail: str, status: str):
    today        = datetime.now().strftime("%Y-%m-%d")
    new_row      = f"| {now_str} | `{operation}` | {detail} | {status} |"
    section_head = (
        f"\n## {today}\n\n"
        f"| 時刻 | 操作 | 内容 | 承認 |\n"
        f"|------|------|------|------|\n"
        f"{new_row}\n"
    )

    if not LOG_FILE.exists():
        LOG_FILE.write_text(
            "# 操作ログ\n\nセキュリティ・外部サービスに関わる操作の記録。\n",
            encoding="utf-8"
        )

    lines   = LOG_FILE.read_text(encoding="utf-8").splitlines()
    section = f"## {today}"

    # 今日の日付セクションが既にある → そのセクションの末尾に挿入
    if any(section in l for l in lines):
        insert_at = len(lines)
        in_section = False
        for i, line in enumerate(lines):
            if section in line:
                in_section = True
            if in_section and line.startswith("## ") and section not in line:
                insert_at = i  # 次のセクションの直前
                break
        lines.insert(insert_at, new_row)
    else:
        lines.append(section_head.rstrip("\n"))

    LOG_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

def _write_to_notion(now: datetime, operation: str, detail: str,
                     approved: bool, category: str):
    try:
        db_id = _get_or_create_log_db()
        notion.pages.create(
            parent={"database_id": db_id},
            properties={
                "操作名":    {"title":     [{"text": {"content": operation}}]},
                "内容":     {"rich_text": [{"text": {"content": detail}}]},
                "カテゴリ": {"select":    {"name": category}},
                "承認":     {"checkbox":   approved},
                "日時":     {"date":       {"start": now.isoformat()}},
            }
        )
    except Exception as e:
        print(f"[警告] Notion記録失敗: {e}")

if __name__ == "__main__":
    args = sys.argv[1:]
    # --notify モード: Discord作業通知のみ
    if args and args[0] == "--notify":
        if len(args) < 2:
            print("使い方: python logger.py --notify <作業内容50文字以内>")
            sys.exit(1)
        notify_work(args[1])
        sys.exit(0)
    # 通常モード: 操作ログ記録
    if len(args) < 2:
        print("使い方: python logger.py <操作名> <内容> [カテゴリ]")
        print("       python logger.py --notify <作業内容50文字以内>")
        sys.exit(1)
    log_operation(
        operation = args[0],
        detail    = args[1],
        approved  = True,
        category  = args[2] if len(args) > 2 else "その他"
    )
