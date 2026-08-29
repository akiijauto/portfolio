import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_text

REPLY_TONES = {
    "丁寧（標準）": "丁寧でフォーマルなビジネスメール調",
    "親しみやすい": "丁寧さを保ちつつ柔らかく親しみやすいトーン",
    "簡潔": "要点のみを簡潔にまとめた短めの文面",
}


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def generate_reply(company: str, contact_name: str, content: str,
                    tone: str, purpose: str = "") -> str:
    """問い合わせ内容に対する返信メール文面をAIで生成する。"""
    tone_desc = REPLY_TONES.get(tone, tone)
    sender = f"{company} {contact_name}様" if contact_name else f"{company}様"

    prompt = f"""以下の問い合わせに対する返信メールの文面を作成してください。

【宛先】{sender}
【問い合わせ内容】
{content}

【返信トーン】{tone_desc}
【返信で伝えたいこと】{purpose or "問い合わせへの感謝、内容を確認した旨、次のステップ（打ち合わせ日程の提案など）の案内"}

件名と本文を含む、そのまま使えるメール文面をテキストで出力してください（前置きや説明は不要）。"""

    return call_claude_text(_client(), "claude-haiku-4-5-20251001", 1000, prompt)
