"""Discord Webhookへの投稿通知。"""
import os
import requests


def send_discord(title: str, description: str, color: int = 5814783) -> bool:
    webhook = os.environ.get("DISCORD_WEBHOOK_URL", "")
    if not webhook:
        return False
    r = requests.post(webhook, json={"embeds": [{"title": title, "description": description, "color": color}]})
    return r.status_code in (200, 204)
