import os
import sys
import logging
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json, call_claude_text

logger = logging.getLogger(__name__)

ARTICLE_TYPES = {
    "解説記事": "読者に概念や仕組みをわかりやすく解説する記事",
    "ハウツー": "手順を追って読者が実践できるようにするHow-to記事",
    "まとめ記事": "複数の情報やツールをリストアップして比較・紹介する記事",
    "事例紹介": "実際の活用事例・ビフォーアフターを紹介する記事",
}

TONES = {
    "丁寧（です/ます体）": "丁寧でプロフェッショナルなです・ます調",
    "カジュアル（だ/である体）": "読みやすくフレンドリーなカジュアル文体",
    "専門的": "専門家向けの正確で詳細な文体",
}


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _create_json(prompt: str, max_tokens: int, retries: int = 2):
    """AIにJSON形式の応答を生成させ、パースして返す。"""
    return call_claude_json(_client(), "claude-haiku-4-5-20251001", max_tokens, prompt, max_retries=retries)


def generate_outline(keyword: str, article_type: str, tone: str,
                     target_chars: int, competitor_context: str = "") -> dict:
    """記事の構成（アウトライン）を生成する。"""
    comp_section = ""
    if competitor_context.strip():
        comp_section = f"\n\n【競合調査の結果（参考）】\n{competitor_context[:1200]}"

    prompt = f"""以下の条件でSEO記事のアウトラインを作成してください。

キーワード: {keyword}
記事タイプ: {article_type}（{ARTICLE_TYPES.get(article_type, '')}）
文体: {tone}
目標文字数: 約{target_chars:,}文字{comp_section}

以下のJSON形式で返してください（Markdown不要、JSONのみ）:
{{
  "title": "記事タイトル（H1）。32文字以内でキーワードを含め、クリックされやすく",
  "meta_desc": "メタディスクリプション。120文字以内でキーワードを含め、読者の行動を促す",
  "intro_hook": "導入部の1文フック（読者の悩みを刺す一文）",
  "sections": [
    {{
      "h2": "H2見出し（20文字以内）",
      "purpose": "このセクションで伝えること（1文）",
      "h3s": ["H3小見出し1", "H3小見出し2"]
    }}
  ],
  "conclusion_point": "まとめセクションで強調すべき核心（1文）",
  "faq": ["よくある質問1", "よくある質問2", "よくある質問3"]
}}

sectionsは5〜7個、各セクションにH3は0〜3個。"""

    # 5〜7セクション分の見出し・目的・H3を含む日本語JSONが
    # 1200トークンでは途中で切れてJSONDecodeErrorになる場合があるため拡大
    return _create_json(prompt, max_tokens=2500)


def generate_article(keyword: str, outline: dict, tone: str,
                     target_chars: int) -> str:
    """アウトラインから記事本文（Markdown）を生成する。"""
    sections_text = "\n".join(
        f"  - H2: {s['h2']}\n    目的: {s['purpose']}\n"
        + ("    H3: " + ", ".join(s.get("h3s", [])) if s.get("h3s") else "")
        for s in outline.get("sections", [])
    )
    faq_text = "\n".join(f"  - {q}" for q in outline.get("faq", []))

    prompt = f"""以下のアウトラインに従って、SEO記事の本文をMarkdown形式で書いてください。

## 条件
- キーワード: {keyword}
- 文体: {tone}
- 目標文字数: 約{target_chars:,}文字
- タイトル（H1）: {outline.get('title', '')}
- 導入フック: {outline.get('intro_hook', '')}

## 構成
{sections_text}

## FAQ
{faq_text}

## 出力ルール
- 最初に `# タイトル` でH1を記述
- 各セクションは `## H2見出し` で始める
- H3は `### 小見出し`
- 導入は200〜300文字で読者の悩みに共感→この記事で解決できると伝える
- 各H2セクションは200〜400文字
- FAQは `## よくある質問` セクションとして最後から2番目に配置
- 最後に `## まとめ` セクション（{outline.get('conclusion_point', '')}）
- キーワード「{keyword}」を自然に5〜8回含める
- Markdown本文のみ出力（説明文不要）"""

    # target_chars最大5000文字の記事本文が3000トークンでは途中で
    # 切れる(記事が完成しない)場合があるため拡大
    return call_claude_text(_client(), "claude-haiku-4-5-20251001", 6000, prompt)
