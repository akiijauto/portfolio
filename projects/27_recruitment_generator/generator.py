import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def generate_recruitment(
    position: str,
    employment_type: str,
    work_schedule: str,
    salary: str,
    job_description: str,
    ideal_candidate: str = "",
    appeal_points: str = "",
) -> dict:
    """募集職種・条件・仕事内容から、求人原稿と面接質問リストをAIに生成させる。"""
    ideal_part = f"\n【求める人物像】\n{ideal_candidate[:500]}" if ideal_candidate else ""
    appeal_part = f"\n【アピールポイント（任意）】\n{appeal_points[:500]}" if appeal_points else ""

    prompt = f"""あなたは店舗・職場の採用活動を支援するアシスタントです。
以下の募集情報から、①応募者向けの求人原稿 と ②面接で使える質問リスト を作成してください。

【募集職種】
{position}

【雇用形態】
{employment_type}

【勤務時間・曜日】
{work_schedule}

【給与・時給】
{salary}

【仕事内容】
{job_description}
{ideal_part}
{appeal_part}

以下のJSON形式で返してください（Markdown不要、JSONのみ）。
入力情報から読み取れない・補足情報がない内容は無理に創作せず、空文字または空配列にしてください。

{{
  "job_posting": {{
    "title": "求人タイトル（職種名を含む、目を引く表現）",
    "catch_copy": "求人原稿の冒頭に置く一言キャッチコピー",
    "job_description": "仕事内容の説明文（2〜4文程度）",
    "requirements": ["応募資格・歓迎条件のリスト"],
    "conditions": ["勤務条件（雇用形態・勤務時間・給与など）のリスト"],
    "appeal_points": ["この職場で働く魅力・アピールポイントのリスト"]
  }},
  "interview_questions": {{
    "basic": ["どの職種にも共通する基本的な質問のリスト（4〜6件）"],
    "role_specific": ["この職種特有の経験・スキルを確認する質問のリスト（3〜5件）"],
    "notes": ["面接で聞くべきではない質問・配慮すべき注意事項（労働局が示す就職差別につながるおそれのある質問など）"]
  }}
}}

interview_questions.notesには、本籍・出生地、家族構成、思想・信条、結婚・出産予定など、
就職差別につながるおそれがあるとして公正な採用選考の観点から避けるべき質問について、
一般的な注意事項を含めてください。
"""
    return call_claude_json(_client(), MODEL, 3000, prompt)
