import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def generate_manual(task_name: str, rough_steps: str, target_audience: str, notes: str = "") -> dict:
    """業務名・ざっくりした手順から、新人教育用の業務マニュアル(SOP)をAIに生成させる。"""
    notes_part = f"\n【その他の補足】\n{notes[:1000]}" if notes else ""

    prompt = f"""あなたは店舗・職場の新人教育マニュアル作成を支援するアシスタントです。
以下の情報から、新人スタッフがそのまま読んで作業できるレベルの業務マニュアル（SOP）を作成してください。

【業務名】
{task_name}

【対象者】
{target_audience}

【ざっくりした手順・メモ】
{rough_steps}
{notes_part}

以下のJSON形式で返してください（Markdown不要、JSONのみ）。
入力情報から読み取れない・補足情報がない内容は無理に創作せず、空文字または空配列にしてください。

{{
  "title": "マニュアルのタイトル",
  "purpose": "この業務を行う目的・なぜ重要かを1〜2文で",
  "preparation": ["作業前に準備するもの・確認することのリスト"],
  "steps": [
    {{"step_no": 1, "title": "手順の見出し", "description": "具体的な作業内容の説明", "tips": "ミスを防ぐコツ・注意点（あれば、なければ空文字）"}}
  ],
  "common_mistakes": ["よくあるミス・トラブルとその対策（入力内容から推測できるもののみ。なければ空配列）"],
  "checklist": ["作業完了時に確認すべき項目のチェックリスト"]
}}

stepsは入力された手順を分かりやすい単位に整理し、5〜10ステップ程度にしてください。
"""
    return call_claude_json(_client(), MODEL, 3000, prompt)
