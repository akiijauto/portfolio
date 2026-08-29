import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def format_report(raw_text: str, staff_name: str = "", report_date: str = "") -> dict:
    """音声入力やメモから日報・引継ぎ事項を整理する。"""
    meta_lines = []
    if report_date:
        meta_lines.append(f"日付: {report_date}")
    if staff_name:
        meta_lines.append(f"記入者: {staff_name}")
    meta = "\n".join(meta_lines)

    prompt = f"""あなたは店舗スタッフの日報・引継ぎメモを整理するアシスタントです。
以下はスタッフが音声入力または手入力した、その日の業務内容のメモです。
口語表現や言い間違い、話し言葉の繰り返しが含まれている場合があります。

{meta}

【入力メモ】
{raw_text[:3000]}

このメモの内容を整理し、以下のJSON形式で返してください（Markdown不要、JSONのみ）。
内容が言及されていない項目は、空文字または空配列にしてください。話の内容を勝手に補完・創作しないでください。

{{
  "summary": "本日の業務全体を2〜3文で要約",
  "sections": {{
    "来客・売上の様子": "言及されていれば整理して記述、なければ空文字",
    "良かった点・うまくいったこと": "言及されていれば整理して記述、なければ空文字",
    "問題・クレーム・トラブル": "言及されていれば整理して記述、なければ空文字",
    "在庫・発注関連": "言及されていれば整理して記述、なければ空文字",
    "その他連絡事項": "言及されていれば整理して記述、なければ空文字"
  }},
  "handover_items": ["翌日以降のスタッフへの引継ぎ事項を箇条書きで（重要度の高い順）。なければ空配列"]
}}
"""
    return call_claude_json(_client(), MODEL, 2000, prompt)
