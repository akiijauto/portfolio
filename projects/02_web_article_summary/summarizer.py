import sys
import os
import anthropic
from pathlib import Path
from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json

load_dotenv()

client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

PROMPT = """以下のWeb記事を要約してください。

URL: {url}
タイトル: {title}

記事本文:
{text}

必ず以下のJSON形式のみで出力してください（説明文不要）：
{{
  "title": "記事タイトル（日本語・30文字以内）",
  "summary_3": ["1文目", "2文目", "3文目"],
  "summary_5": ["1文目", "2文目", "3文目", "4文目", "5文目"],
  "sns": "SNS投稿用200文字以内（ハッシュタグ2〜3個含む）"
}}"""

def summarize(url: str, text: str, title: str) -> dict:
    """テキストをClaudeで要約してdict形式で返す。"""
    prompt = PROMPT.format(url=url, title=title, text=text[:4000])
    return call_claude_json(client, "claude-haiku-4-5-20251001", 3072, prompt)
