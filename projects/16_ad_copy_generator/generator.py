import os
import sys
import logging
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

logger = logging.getLogger(__name__)

PLATFORMS = ["Google検索広告", "Meta広告", "LINE広告"]

AD_LIMITS = {
    "Google検索広告": {
        "headline_max_chars": 30, "headline_count": 10,
        "desc_max_chars": 90,    "desc_count": 4,
    },
    "Meta広告": {
        "primary_max": 125, "headline_max": 40, "desc_max": 30,
    },
    "LINE広告": {
        "title_max": 40, "text_max": 240,
    },
}

GOALS = {
    "認知拡大": "まず知ってもらう・ブランド認知を高める",
    "リード獲得": "問い合わせ・資料請求・登録を促す",
    "購入・成約": "商品購入・契約・申し込みに直結させる",
    "来店・予約": "店舗来店・予約・イベント参加を促す",
}


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _create_json(prompt: str, max_tokens: int, retries: int = 2):
    """AIにJSON形式の応答を生成させ、パースして返す。"""
    return call_claude_json(_client(), "claude-haiku-4-5-20251001", max_tokens, prompt, max_retries=retries)


def generate_all(product: str, target: str, usp: str,
                 industry: str, goal: str) -> dict:
    """全プラットフォームの広告文を一括生成する。"""
    goal_desc = GOALS.get(goal, goal)

    prompt = f"""以下の商品・サービスの広告文を3媒体分、一括で作成してください。

【商品・サービス名】{product}
【ターゲット】{target}
【強み・USP】{usp}
【業界】{industry or "指定なし"}
【広告目的】{goal}（{goal_desc}）

以下のJSON形式で返してください（説明文不要、JSONのみ）:
{{
  "google": {{
    "headlines": ["見出し1（30文字以内）", "見出し2", ...(10本)],
    "descriptions": ["説明文1（90文字以内）", "説明文2", "説明文3", "説明文4"]
  }},
  "meta": {{
    "primary_text": "プライマリテキスト（125文字以内、改行OK）",
    "headline": "見出し（40文字以内）",
    "description": "説明文（30文字以内）",
    "cta_options": ["ボタンCTA案1", "ボタンCTA案2", "ボタンCTA案3"]
  }},
  "line": {{
    "title": "タイトル（40文字以内）",
    "text": "広告テキスト（240文字以内）"
  }},
  "ab_variants": {{
    "google_alt_headline": "Googleの別バリエーション見出し（感情訴求 or 数字強調）",
    "meta_alt_primary": "Metaの別バリエーション本文（異なる切り口で）"
  }},
  "copy_points": "この広告文が効果的な理由を2〜3文で解説"
}}

各媒体の特性に合わせてください:
- Google: 検索意図に直接応える・キーワードを含める・具体的数字を使う
- Meta: 感情に訴える・スクロールを止めるフック・ストーリー性
- LINE: 親しみやすく・地域密着感・行動を促す"""

    # 3媒体分(Google10見出し+4説明文/Meta/LINE/AB案)の日本語JSONは
    # 1500トークンでは途中で切れてJSONDecodeErrorになる場合があるため拡大
    return _create_json(prompt, max_tokens=4096)
