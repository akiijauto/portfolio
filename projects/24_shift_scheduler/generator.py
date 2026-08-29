import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


DAYS = ["月", "火", "水", "木", "金", "土", "日"]


def generate_shift(staff: list[dict], requirements: list[dict], notes: str = "") -> dict:
    """スタッフの希望条件と曜日別の必要人数から、1週間分のシフト案をAIに生成させる。"""
    staff_lines = []
    for s in staff:
        staff_lines.append(
            f"- {s['name']}: 出勤可能曜日=[{s['available_days']}] / 希望勤務時間={s['preferred_hours']} "
            f"/ 週の上限時間={s['max_hours']}時間"
        )
    staff_text = "\n".join(staff_lines)

    req_lines = []
    for r in requirements:
        req_lines.append(
            f"- {r['day']}: 営業時間={r['open_hours']} / 必要人数={r['required_count']}人"
        )
    req_text = "\n".join(req_lines)

    notes_part = f"\n【追加の考慮事項】\n{notes[:1000]}" if notes else ""

    prompt = f"""あなたは店舗のシフト作成を支援するアシスタントです。
以下のスタッフの希望条件と、曜日別の必要人数・営業時間をもとに、1週間分のシフト案を作成してください。

【スタッフ一覧】
{staff_text}

【曜日別 必要人数・営業時間】
{req_text}
{notes_part}

作成にあたっては以下に注意してください。
- スタッフの出勤可能曜日・希望勤務時間・週の上限時間を尊重する
- 1日6時間を超える勤務には45分以上、8時間を超える勤務には1時間以上の休憩が必要（労働基準法）。
  休憩時間の確保が難しい場合や、必要人数を満たせない曜日がある場合は、断定せず「concerns」に記載する
- 特定のスタッフに負担が偏らないよう、可能な範囲で公平に割り振る

以下のJSON形式で返してください（Markdown不要、JSONのみ）。
データから判断できない・確認が必要な内容は無理に記載せず、空文字または空配列にしてください。

{{
  "shift_plan": [
    {{
      "day": "月",
      "assignments": [
        {{"name": "スタッフ名", "time": "09:00-17:00", "break": "12:00-13:00"}}
      ],
      "staffing_ok": true,
      "note": "この曜日特有の補足（あれば）"
    }}
  ],
  "concerns": ["労働時間・必要人数などで確認が必要な点（あれば）。なければ空配列"],
  "suggestions": ["シフト作成・運用上の改善提案（あれば）。なければ空配列"]
}}

shift_planは{', '.join(DAYS)}の順に7曜日すべて含めてください。該当曜日に営業時間の指定がない場合はassignmentsを空配列にしてください。
"""
    return call_claude_json(_client(), MODEL, 3000, prompt)
