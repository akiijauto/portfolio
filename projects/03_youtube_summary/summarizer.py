import sys
import os
import anthropic
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PROMPT = """以下のYouTube動画の字幕テキストを要約してください。

動画タイトル: {title}
URL: {url}

字幕テキスト（先頭4000文字）:
{transcript}

必ず以下のJSON形式のみで出力してください（余分なテキスト不要）：
{{
  "summary": "動画全体の要約（100〜150文字）",
  "points": ["ポイント1", "ポイント2", "ポイント3", "ポイント4", "ポイント5"],
  "sns": "SNS投稿用200文字以内（ハッシュタグ2〜3個含む）",
  "category": "動画のカテゴリ（例: テクノロジー・ビジネス・エンタメ等）"
}}"""

def summarize(url: str, title: str, transcript: str) -> dict:
    prompt = PROMPT.format(title=title, url=url, transcript=transcript[:4000])
    return call_claude_json(client, "claude-haiku-4-5-20251001", 3072, prompt)
