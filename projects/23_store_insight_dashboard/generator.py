import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def analyze_insights(records: list[dict], notes: str = "") -> dict:
    """日次の店舗データと現場メモから、改善インサイトをAIに生成させる。"""
    rows = []
    for r in records:
        rows.append(
            f"{r['date']} | 売上: {r['sales']}円 | 客数: {r['customers']}人 "
            f"| 客単価: {r['sales'] // r['customers'] if r['customers'] else 0}円 "
            f"| スタッフ人数: {r['staff']}人"
        )
    table_text = "\n".join(rows)

    notes_part = f"\n【現場からのメモ・気づき】\n{notes[:1000]}" if notes else ""

    prompt = f"""あなたは店舗運営の改善を支援するコンサルタントです。
以下は店舗の日次データと現場からのメモです。データの傾向を分析し、改善インサイトを提示してください。

【日次データ】
{table_text}
{notes_part}

以下のJSON形式で返してください（Markdown不要、JSONのみ）。
データから読み取れない・断定できない内容は無理に記載せず、空文字または空配列にしてください。

{{
  "trend_summary": "売上・客数・客単価の傾向を2〜3文で要約",
  "good_points": ["データやメモから読み取れる良い傾向・うまくいっている点（あれば）。なければ空配列"],
  "concern_points": ["データやメモから読み取れる気になる点・課題（あれば）。なければ空配列"],
  "improvement_actions": [
    {{"title": "改善アクションのタイトル", "description": "具体的な内容", "priority": "高 または 中 または 低"}}
  ]
}}

improvement_actionsは2〜4件程度にし、優先度の高いものから順に並べてください。
"""
    return call_claude_json(_client(), MODEL, 2000, prompt)
