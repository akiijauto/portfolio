import sys
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

load_dotenv()

CONDITIONS = {
    "新品、未使用":         "未開封・未使用の新品",
    "未使用に近い":         "ほぼ未使用・使用回数が少なく傷や汚れなし",
    "目立った傷や汚れなし": "普通に使用・目立つ傷や汚れなし",
    "やや傷や汚れあり":     "使用感あり・細かい傷や汚れが数箇所",
    "傷や汚れあり":         "目立つ傷や汚れあり・使用感が強い",
    "全体的に状態が悪い":   "かなり使用感あり・目立つダメージあり",
}

PROMPT = """メルカリで売れる出品文を作成してください。

商品名: {name}
状態: {condition}（{condition_detail}）
カテゴリ: {category}
特徴・付属品・補足: {features}

必ず以下のJSON形式のみで出力してください：
{{
  "title": "40文字以内のタイトル（商品名＋状態＋特徴を凝縮）",
  "description": "出品文（300〜500文字）。状態説明・特徴・注意事項・取引についてを含める",
  "price_min": 推奨最低価格（円・数値のみ）,
  "price_max": 推奨最高価格（円・数値のみ）,
  "category": "メルカリのカテゴリ名",
  "tips": ["売るためのコツ1", "コツ2", "コツ3"]
}}"""

def generate_listing(name: str, condition: str, category: str, features: str) -> dict:
    condition_detail = CONDITIONS.get(condition, condition)
    prompt = PROMPT.format(
        name=name, condition=condition, condition_detail=condition_detail,
        category=category or "自動判定", features=features or "特になし"
    )
    return call_claude_json(None, "claude-haiku-4-5-20251001", 3072, prompt)
