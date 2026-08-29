import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

MODEL = "claude-haiku-4-5-20251001"


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def predict_reorder(items: list[dict], notes: str = "") -> dict:
    """商品ごとの在庫・消費ペース・発注リードタイムから、発注タイミングをAIに予測させる。"""
    rows = []
    for it in items:
        rows.append(
            f"- {it['name']}: 現在の在庫={it['current_stock']}個 / 1日あたりの平均消費量={it['avg_daily_usage']}個 "
            f"/ 発注リードタイム={it['lead_time_days']}日 / 発注ロット={it['order_lot']}個"
        )
    items_text = "\n".join(rows)

    notes_part = f"\n【追加の考慮事項】\n{notes[:1000]}" if notes else ""

    prompt = f"""あなたは店舗の在庫管理を支援するアシスタントです。
以下の商品ごとの在庫状況・消費ペース・発注リードタイムから、発注タイミングと推奨発注量を予測してください。

【商品一覧】
{items_text}
{notes_part}

予測にあたっては以下の考え方を使ってください。
- 在庫がなくなるまでの予測日数 = 現在の在庫 ÷ 1日あたりの平均消費量
- 発注リードタイム期間中に欠品しないよう、「在庫がなくなるまでの予測日数 - 発注リードタイム」が
  0に近い、またはマイナスの商品は早急な発注が必要
- 推奨発注量は、発注ロットが指定されている場合はその倍数に近い値を提案する

以下のJSON形式で返してください（Markdown不要、JSONのみ）。
データから判断できない・確認が必要な内容は無理に記載せず、空文字または空配列にしてください。

{{
  "items": [
    {{
      "name": "商品名",
      "days_until_stockout": 在庫が尽きるまでの予測日数(数値、小数可),
      "urgency": "緊急 または 早めに発注 または 様子見",
      "reorder_advice": "発注タイミングに関する具体的なアドバイス（1〜2文）",
      "recommended_order_qty": 推奨発注量(数値),
      "note": "この商品特有の補足（あれば、なければ空文字）"
    }}
  ],
  "overall_concerns": ["在庫全体で気になる点（あれば）。なければ空配列"],
  "suggestions": ["在庫管理運用の改善提案（あれば）。なければ空配列"]
}}

itemsは入力された商品の順に、urgencyが「緊急」のものが分かりやすいようすべて出力してください。
"""
    return call_claude_json(_client(), MODEL, 3000, prompt)
