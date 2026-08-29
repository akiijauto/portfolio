"""APSchedulerによる定期実行とDiscord配信。"""
import os
import sys
import threading
from datetime import datetime
from pathlib import Path

import pytz
import requests
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger

sys.path.insert(0, str(Path(__file__).parents[2] / "projects" / "08_api_hub"))
from fetchers import fetch_weather, fetch_exchange

JST = pytz.timezone("Asia/Tokyo")
JOB_ID = "daily_digest"

# 実行ログ（スレッド間共有、ロックで保護）
_log: list = []
_lock = threading.Lock()

# スケジューラシングルトン
_scheduler: BackgroundScheduler | None = None
_schedule_state = {"hour": 8, "minute": 0}  # 現在の設定を保持


def _add_log(status: str, summary: str):
    entry = {
        "at": datetime.now(JST).strftime("%Y-%m-%d %H:%M:%S"),
        "status": status,
        "summary": summary,
    }
    with _lock:
        _log.insert(0, entry)
        if len(_log) > 5:
            _log.pop()


def _build_message() -> str:
    now = datetime.now(JST).strftime("%Y/%m/%d (%a) %H:%M JST")
    lines = [f"**🌅 デイリーダイジェスト — {now}**", ""]

    w = fetch_weather("Tokyo")
    if w["ok"]:
        lines.append(f"🌤 **天気（東京）**：{w['weather']} / {w['temp']}°C / 風速{w['wind']}km/h")
    else:
        lines.append(f"🌤 **天気**：取得失敗（{w['error']}）")

    ex = fetch_exchange("USD", "JPY", 1)
    if ex["ok"]:
        lines.append(f"💴 **USD/JPY**：1ドル = {ex['rate']}円（{ex['date']} 時点）")
    else:
        lines.append(f"💴 **USD/JPY**：取得失敗（{ex['error']}）")

    return "\n".join(lines)


def run_digest() -> dict:
    """配信ジョブ本体。Flask ルートとスケジューラの両方から呼ぶ。"""
    url = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not url:
        _add_log("error", "DISCORD_WEBHOOK_URL が未設定")
        return {"ok": False, "error": "DISCORD_WEBHOOK_URL が .env に設定されていません。"}

    try:
        message = _build_message()
        r = requests.post(url, json={"content": message}, timeout=10)
        r.raise_for_status()
        _add_log("success", "Discord に配信完了")
        return {"ok": True, "message": message}
    except requests.RequestException as e:
        _add_log("error", f"Discord 送信失敗: {e}")
        return {"ok": False, "error": f"Discord への送信に失敗しました。（{e}）"}
    except Exception as e:
        _add_log("error", f"ジョブ例外: {e}")
        return {"ok": False, "error": str(e)}


def get_logs() -> list:
    with _lock:
        return list(_log)


def get_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = BackgroundScheduler(timezone=JST)
        _scheduler.start()
    return _scheduler


def get_job_info() -> dict:
    sched = get_scheduler()
    job = sched.get_job(JOB_ID)
    if job is None:
        return {"scheduled": False, "next_run": None, **_schedule_state}
    return {
        "scheduled": True,
        "next_run": job.next_run_time.strftime("%Y-%m-%d %H:%M %Z") if job.next_run_time else None,
        **_schedule_state,
    }


def set_schedule(hour: int, minute: int):
    _schedule_state["hour"] = hour
    _schedule_state["minute"] = minute
    sched = get_scheduler()
    sched.remove_job(JOB_ID) if sched.get_job(JOB_ID) else None
    sched.add_job(
        run_digest,
        CronTrigger(hour=hour, minute=minute, timezone=JST),
        id=JOB_ID,
        name="daily_digest",
        replace_existing=True,
    )


def remove_schedule():
    sched = get_scheduler()
    if sched.get_job(JOB_ID):
        sched.remove_job(JOB_ID)
