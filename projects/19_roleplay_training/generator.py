import os
import sys
from pathlib import Path

import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_chat, call_claude_json

MODEL = "claude-haiku-4-5-20251001"

SCENARIOS = {
    "food_complaint": {
        "label": "料理に異物が入っていたというクレーム",
        "industry": "飲食店",
        "persona": (
            "あなたは飲食店の客です。先ほど提供された料理に髪の毛のような異物が入っているのを見つけ、"
            "強い不快感を持っています。最初は冷静に事実を伝えますが、"
            "スタッフの対応が誠実でなかったり言い訳に聞こえたりすると、徐々に語気が強くなります。"
            "謝罪と具体的な対応（作り直し・会計対応など）が示されれば態度は軟化します。"
        ),
    },
    "discount_demand": {
        "label": "常連だからと理不尽な割引・特別対応を要求",
        "industry": "店舗共通",
        "persona": (
            "あなたは「このお店の常連客」だと主張する客です。"
            "「いつも来ているのだから割引してほしい」「前は店長が特別に対応してくれた」などと、"
            "規定にない割引やサービスを要求します。"
            "スタッフが規定通りに丁寧に説明すれば次第に納得しますが、"
            "曖昧な対応や即答での拒否には不満を強めます。"
        ),
    },
    "foreign_tourist": {
        "label": "言葉が伝わりにくい外国人観光客への対応",
        "industry": "飲食店・宿泊",
        "persona": (
            "あなたは日本語があまり話せない外国人観光客です。"
            "簡単な日本語と英語を混ぜながら話します（例: 'Sorry, English OK? メニュー、わからない'）。"
            "アレルギー対応や会計、部屋・席の希望など、伝えたいことがうまく伝わらず困っています。"
            "スタッフが簡単な言葉やジェスチャーの提案などで分かりやすく対応してくれると安心して会話が進みます。"
        ),
    },
    "long_wait": {
        "label": "予約時間より長時間待たされたことへの不満",
        "industry": "飲食店・サロン",
        "persona": (
            "あなたは予約時間より20分以上待たされている客です。"
            "時間に対して苛立っており、「予約した意味がない」と感じています。"
            "スタッフが状況をきちんと説明し謝罪すれば落ち着きますが、"
            "「少々お待ちください」を繰り返すだけの対応にはさらに不満を強めます。"
        ),
    },
    "product_defect": {
        "label": "購入した商品が不良品だったという返品・交換要求",
        "industry": "小売店",
        "persona": (
            "あなたは数日前に購入した商品が初期不良だったため、返品・交換を求める客です。"
            "レシートは手元にありますが、開封済みです。"
            "スタッフが規定に基づいて落ち着いて案内すれば納得しますが、"
            "「開封済みだから対応できない」とだけ言われると強く反論します。"
        ),
    },
}

DIFFICULTIES = {
    "normal": "口調は厳しめですが、誠実な対応にはきちんと応じる、標準的な難易度の客です。",
    "hard": "口調が強く威圧的で、簡単には納得しません。曖昧な対応には鋭く突っ込みを入れる、難易度の高い客です。",
}


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _system_prompt(scenario_key: str, difficulty: str) -> str:
    scenario = SCENARIOS[scenario_key]
    diff = DIFFICULTIES.get(difficulty, DIFFICULTIES["normal"])
    return f"""あなたは接客研修のロールプレイで「客」役を演じるAIです。
業種: {scenario['industry']}
シチュエーション: {scenario['label']}
あなたが演じる客の人物像: {scenario['persona']}
難易度: {diff}

【ルール】
- あなたは常に「客」として話してください。スタッフ側のセリフや説明、AIとしての発言は一切しないでください。
- 1回の発言は2〜4文程度の自然な会話文にしてください。
- スタッフの対応の質に応じて態度（口調・納得度）を変化させてください。
- 過度に暴力的・差別的な発言はしないでください。
"""


def _history_to_messages(history: list[dict]) -> list[dict]:
    messages = []
    for turn in history:
        role = "assistant" if turn.get("speaker") == "customer" else "user"
        messages.append({"role": role, "content": turn.get("text", "")})
    return messages


def start_conversation(scenario_key: str, difficulty: str) -> str:
    """ロールプレイの冒頭、客側からの最初の発言を生成する。"""
    system = _system_prompt(scenario_key, difficulty)
    messages = [{"role": "user", "content": "（スタッフが対応に来ました。客として最初の発言をしてください）"}]
    return call_claude_chat(_client(), MODEL, 300, system, messages)


def continue_conversation(scenario_key: str, difficulty: str, history: list[dict]) -> str:
    """スタッフの発言を受けて、客側の次の発言を生成する。"""
    system = _system_prompt(scenario_key, difficulty)
    messages = _history_to_messages(history)
    return call_claude_chat(_client(), MODEL, 300, system, messages)


def score_conversation(scenario_key: str, difficulty: str, history: list[dict]) -> dict:
    """ロールプレイ全体のやり取りを採点し、フィードバックを返す。"""
    scenario = SCENARIOS[scenario_key]
    transcript = "\n".join(
        f"{'客' if t.get('speaker') == 'customer' else 'スタッフ'}: {t.get('text', '')}"
        for t in history
    )

    prompt = f"""あなたは接客研修の評価担当者です。以下は新人スタッフが「{scenario['label']}」（{scenario['industry']}）のロールプレイ研修を行った会話ログです。

【会話ログ】
{transcript[:4000]}

スタッフの対応を評価し、以下のJSON形式で返してください（Markdown不要、JSONのみ）:
{{
  "scores": {{
    "傾聴・共感": 0〜5の整数,
    "謝罪・誠意": 0〜5の整数,
    "説明の分かりやすさ": 0〜5の整数,
    "提案・解決力": 0〜5の整数,
    "言葉遣い・態度": 0〜5の整数
  }},
  "total_comment": "総合評価コメント（2〜3文）",
  "good_points": ["良かった点を箇条書きで2〜3個"],
  "improvement_points": ["改善点を箇条書きで2〜3個"],
  "model_answer": "この場面でより良い対応をする場合の、スタッフのセリフ例を1〜2文で"
}}
"""
    return call_claude_json(_client(), MODEL, 1500, prompt)
