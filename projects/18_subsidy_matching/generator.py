import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def match_subsidy(business_desc: str, subsidy: dict) -> dict:
    """事業内容と補助金情報を照合し、適合度を診断する。"""
    prompt = f"""あなたは中小企業の補助金申請支援の専門家です。
以下の「事業者の事業内容」が、「補助金・助成金の概要」にどの程度適合しているかを診断してください。

【事業者の事業内容】
{business_desc[:1500]}

【補助金・助成金の情報】
タイトル: {subsidy['title']}
対象エリア: {subsidy.get('target_area_detail', '')}
対象従業員数: {subsidy.get('target_number_of_employees', '')}
利用目的: {subsidy.get('use_purpose', '')}
対象業種: {subsidy.get('industry', '')}
上限額: {subsidy.get('subsidy_max_limit', '不明')}
概要本文:
{subsidy.get('detail_text', '')[:2500]}

以下のJSON形式で診断結果のみを返してください（Markdown不要）:
{{
  "score": 適合度を0〜100の整数で,
  "score_label": "score に対応する一言評価（例: 高い適合性が見込めます／要件確認が必要です／適合度は低めです）",
  "reasons": ["適合していると考えられる理由を箇条書きで2〜4個"],
  "concerns": ["申請前に確認すべき注意点・懸念点を箇条書きで1〜4個"],
  "required_documents": ["申請時に必要となりそうな書類を箇条書きで3〜6個（一般的に求められるものを推定）"],
  "next_action": "次に取るべきアクションを1〜2文で"
}}
"""
    return call_claude_json(_client(), MODEL, 1500, prompt)


def generate_business_plan(business_desc: str, subsidy: dict, focus_points: str = "") -> dict:
    """選択した補助金に向けた事業計画書ドラフトを生成する。"""
    focus_section = ""
    if focus_points.strip():
        focus_section = f"\n\n【事業計画で特に重視したい点（任意入力）】\n{focus_points[:500]}"

    prompt = f"""あなたは中小企業診断士として、補助金申請用の事業計画書のドラフトを作成します。

【事業者の事業内容】
{business_desc[:1500]}

【申請を検討している補助金・助成金】
タイトル: {subsidy['title']}
利用目的: {subsidy.get('use_purpose', '')}
対象業種: {subsidy.get('industry', '')}
上限額: {subsidy.get('subsidy_max_limit', '不明')}
概要本文:
{subsidy.get('detail_text', '')[:2500]}{focus_section}

上記の補助金の趣旨に合致するよう、事業計画書のドラフトを以下のJSON形式で作成してください（Markdown不要、JSONのみ）:
{{
  "title": "事業計画のタイトル（30文字以内）",
  "overview": "事業概要（200〜300文字程度）",
  "current_issues": "現状の課題・背景（200文字程度）",
  "solution": "課題に対する解決策・実施内容（300文字程度。補助金の対象事業との関連を明記）",
  "schedule": [
    {{"phase": "フェーズ名（例: 準備・発注）", "period": "想定期間（例: 交付決定後1ヶ月目）", "content": "実施内容"}}
  ],
  "expected_costs": [
    {{"item": "経費項目", "estimate": "概算金額（例: 約80万円）", "note": "補足"}}
  ],
  "expected_effects": "期待される効果（数値目標を含め200文字程度）",
  "application_tips": ["申請時に強調すべきポイントを箇条書きで2〜4個"]
}}

scheduleは3〜5項目、expected_costsは2〜5項目程度で作成してください。
"""
    return call_claude_json(_client(), MODEL, 2500, prompt)
