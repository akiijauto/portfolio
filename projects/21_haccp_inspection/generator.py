import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_vision_json

MODEL = "claude-haiku-4-5-20251001"

CATEGORIES = {
    "fridge_temp": "冷蔵・冷凍庫の温度表示",
    "cleaning":    "調理台・作業エリアの清掃状況",
    "storage":     "食材の保管状態（容器・ラップ・期限表示など）",
    "handwash":    "手洗い・消毒設備",
    "waste":       "ゴミ箱・排水口の管理状況",
    "staff":       "スタッフの服装・衛生（帽子・手袋など）",
    "other":       "その他",
}


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def inspect_photo(image_b64: str, media_type: str, category_key: str, notes: str = "") -> dict:
    """写真を分析し、HACCP点検記録用の判定・コメントを生成する。"""
    category_label = CATEGORIES.get(category_key, CATEGORIES["other"])

    notes_part = f"\nスタッフからの補足コメント: {notes[:300]}" if notes else ""

    prompt_text = f"""あなたは飲食店・店舗のHACCP（食品衛生管理）点検をサポートするアシスタントです。
以下の写真は「{category_label}」の点検対象を撮影したものです。{notes_part}

写真から確認できる内容に基づいて点検を行い、以下のJSON形式で返してください（Markdown不要、JSONのみ）。
写真から判断できない項目は、無理に断定せず「写真から確認できません」としてください。

{{
  "observation": "写真から確認できる内容を客観的に2〜3文で説明",
  "checks": [
    {{"item": "確認したチェック項目名", "result": "OK または 要注意 または NG または 確認不可", "comment": "判定理由・補足"}}
  ],
  "overall_judgement": "OK または 要注意 または NG",
  "issues": ["写真から確認できる衛生上の問題点（あれば）。なければ空配列"],
  "corrective_actions": ["問題点に対する改善アクション（あれば）。なければ空配列"],
  "record_comment": "HACCP点検記録表に記入できる一言コメント（1〜2文）"
}}

checksは点検対象に応じて2〜4項目程度にしてください。
"""

    return call_claude_vision_json(_client(), MODEL, 1500, image_b64, media_type, prompt_text)
