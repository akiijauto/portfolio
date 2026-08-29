"""
全プロジェクト共通ユーティリティ。

使い方:
    import sys
    from pathlib import Path
    sys.path.insert(0, str(Path(__file__).parents[2]))  # AI開発/
    from shared.utils import extract_json, call_claude_json
"""
import json
import os
import re
import time

import anthropic

# Claude APIの一時的なエラー（混雑・タイムアウト・接続エラー）はリトライで自動回復を試みる
TRANSIENT_ANTHROPIC_ERRORS = (
    anthropic.RateLimitError,
    anthropic.APIConnectionError,
    anthropic.APITimeoutError,
    anthropic.InternalServerError,
)

# AI_PROVIDER=gemini にすると、Claude向けに書かれた呼び出しコードを変更せずGemini APIに切り替えられる。
# 既存プロジェクトは全てclaude-haiku-4-5-20251001を使っているため、対応表は1エントリのみ。
AI_PROVIDER = os.environ.get("AI_PROVIDER", "gemini").lower()

CLAUDE_TO_GEMINI_MODEL = {
    "claude-haiku-4-5-20251001": "gemini-2.5-flash",
}

_gemini_client = None


def _get_gemini_client():
    global _gemini_client
    if _gemini_client is None:
        from google import genai
        _gemini_client = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
    return _gemini_client


def _call_gemini_json(model: str, max_tokens: int, prompt: str, max_retries: int) -> dict | list:
    from google.genai import types

    gemini_model = CLAUDE_TO_GEMINI_MODEL.get(model, "gemini-2.5-flash")
    client = _get_gemini_client()

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=gemini_model,
                contents=prompt,
                # thinking_budget=0: 「思考」トークンがmax_output_tokensを消費して
                # JSON応答が途中で切れる(truncate)のを防ぐため、思考機能を無効化する。
                config=types.GenerateContentConfig(
                    max_output_tokens=max_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        try:
            return extract_json(response.text)
        except ValueError as e:
            last_error = e
    raise last_error


def _call_gemini_chat(model: str, max_tokens: int, system: str | None,
                       messages: list[dict], max_retries: int) -> str:
    from google.genai import types

    gemini_model = CLAUDE_TO_GEMINI_MODEL.get(model, "gemini-2.5-flash")
    client = _get_gemini_client()

    contents = [
        {"role": "model" if m["role"] == "assistant" else "user",
         "parts": [{"text": m["content"]}]}
        for m in messages
    ]
    config_kwargs = {
        "max_output_tokens": max_tokens,
        "thinking_config": types.ThinkingConfig(thinking_budget=0),
    }
    if system:
        config_kwargs["system_instruction"] = system
    config = types.GenerateContentConfig(**config_kwargs)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=gemini_model, contents=contents, config=config,
            )
            return (response.text or "").strip()
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_error


def _call_gemini_vision_json(model: str, max_tokens: int, image_b64: str,
                              media_type: str, prompt: str, max_retries: int) -> dict | list:
    import base64
    from google.genai import types

    gemini_model = CLAUDE_TO_GEMINI_MODEL.get(model, "gemini-2.5-flash")
    client = _get_gemini_client()

    contents = [{
        "role": "user",
        "parts": [
            {"inline_data": {"mime_type": media_type, "data": base64.b64decode(image_b64)}},
            {"text": prompt},
        ],
    }]
    config = types.GenerateContentConfig(
        max_output_tokens=max_tokens,
        thinking_config=types.ThinkingConfig(thinking_budget=0),
    )

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            response = client.models.generate_content(
                model=gemini_model, contents=contents, config=config,
            )
        except Exception as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        try:
            return extract_json(response.text)
        except ValueError as e:
            last_error = e
    raise last_error


def extract_json(text: str) -> dict | list:
    """Claude APIレスポンスからJSONを安全に抽出する。

    コードブロック（```json）・前後の余分なテキストを除去してパースする。
    dict と list 両方に対応。
    """
    text = text.strip()

    # ```json ... ``` 形式のコードブロックを除去
    text = re.sub(r"```json\s*", "", text)
    text = re.sub(r"```\s*",     "", text)

    obj_start = text.find("{")
    arr_start = text.find("[")

    if obj_start == -1 and arr_start == -1:
        raise ValueError(f"JSONが見つかりません: {text[:120]}")

    # object か array か、先に現れた方を選ぶ
    use_array = (arr_start != -1) and (obj_start == -1 or arr_start < obj_start)

    if use_array:
        end = text.rfind("]") + 1
        raw = text[arr_start:end]
    else:
        end = text.rfind("}") + 1
        raw = text[obj_start:end]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as e:
        raise ValueError(f"JSONのパースに失敗しました: {e}\n抽出部分: {raw[:200]}") from e


def call_claude_json(
    client,
    model: str,
    max_tokens: int,
    prompt: str,
    max_retries: int = 2,
    cache_prefix: str | None = None,
) -> dict | list:
    """Claudeを呼び出し、JSON応答を抽出する。

    - 一時的なAPIエラー（混雑・タイムアウト・接続エラー）は待機して再試行する（Project 13と同じパターン）。
    - 応答が途中で切れる・構文エラーになるなど `extract_json` が失敗した場合も、
      最大 `max_retries` 回まで再呼び出しする（Project 13〜16と同じリトライパターン）。
    - `cache_prefix` を指定すると、固定の指示文（プロンプトテンプレートなど）を
      `cache_control: ephemeral` 付きの別ブロックとして送信し、同一内容が
      繰り返し呼ばれる場合にAnthropicのprompt cachingでコストを削減できる
      （キャッシュ対象は一定トークン数以上である必要がある）。
    - 環境変数 `AI_PROVIDER=gemini` が設定されている場合、`client`/`model` 引数は無視され、
      代わりにGemini APIを呼び出す（呼び出し元のコードは変更不要）。
    """
    if AI_PROVIDER == "gemini":
        return _call_gemini_json(model, max_tokens, prompt, max_retries)

    if cache_prefix:
        content = [
            {"type": "text", "text": cache_prefix, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": prompt},
        ]
    else:
        content = prompt

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
        except TRANSIENT_ANTHROPIC_ERRORS as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        try:
            return extract_json(message.content[0].text)
        except ValueError as e:
            last_error = e
    raise last_error


def call_claude_text(
    client,
    model: str,
    max_tokens: int,
    prompt: str,
    max_retries: int = 2,
    cache_prefix: str | None = None,
) -> str:
    """Claudeを呼び出し、テキスト応答をそのまま返す（JSON変換なし）。

    要約・記事本文・メール文面など、JSON形式が不要な自由文生成に使う。
    `AI_PROVIDER=gemini` の場合はGeminiを呼び出す（call_claude_jsonと同じ切替方式）。
    """
    if AI_PROVIDER == "gemini":
        return _call_gemini_chat(model, max_tokens, None, [{"role": "user", "content": prompt}], max_retries)

    if cache_prefix:
        content = [
            {"type": "text", "text": cache_prefix, "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": prompt},
        ]
    else:
        content = prompt

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": content}],
            )
            return message.content[0].text.strip()
        except TRANSIENT_ANTHROPIC_ERRORS as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_error


def call_claude_chat(
    client,
    model: str,
    max_tokens: int,
    system: str,
    messages: list[dict],
    max_retries: int = 2,
) -> str:
    """システムプロンプト＋複数ターンの会話履歴から、AIの次の発言を生成する。

    ロールプレイ等、文脈を引き継いだ複数ターンの対話生成に使う。
    `AI_PROVIDER=gemini` の場合はGeminiを呼び出す。
    """
    if AI_PROVIDER == "gemini":
        return _call_gemini_chat(model, max_tokens, system, messages, max_retries)

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            message = client.messages.create(
                model=model,
                max_tokens=max_tokens,
                system=system,
                messages=messages,
            )
            return message.content[0].text.strip()
        except TRANSIENT_ANTHROPIC_ERRORS as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
    raise last_error


def call_claude_vision_json(
    client,
    model: str,
    max_tokens: int,
    image_b64: str,
    media_type: str,
    prompt: str,
    max_retries: int = 2,
) -> dict | list:
    """画像＋テキストプロンプトを送り、JSON応答を抽出する。

    写真ベースの点検・診断機能に使う。`AI_PROVIDER=gemini` の場合はGeminiを呼び出す。
    """
    if AI_PROVIDER == "gemini":
        return _call_gemini_vision_json(model, max_tokens, image_b64, media_type, prompt, max_retries)

    messages = [{
        "role": "user",
        "content": [
            {"type": "image", "source": {"type": "base64", "media_type": media_type, "data": image_b64}},
            {"type": "text", "text": prompt},
        ],
    }]

    last_error = None
    for attempt in range(max_retries + 1):
        try:
            message = client.messages.create(model=model, max_tokens=max_tokens, messages=messages)
        except TRANSIENT_ANTHROPIC_ERRORS as e:
            last_error = e
            if attempt < max_retries:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        try:
            return extract_json(message.content[0].text)
        except ValueError as e:
            last_error = e
    raise last_error


def is_credit_error(e: Exception) -> bool:
    """Anthropicのクレジット残高不足エラーかどうかを判定する。"""
    return isinstance(e, anthropic.BadRequestError) and "credit balance" in str(e).lower()


def handle_ai_error(e: Exception, project_name: str) -> str:
    """AI呼び出し時の例外を利用者向けエラーメッセージに変換する。

    クレジット残高不足の場合は、利用者には「一時的にサービス提供を中断している」旨の
    謝罪文を表示し、管理者へ通知（メール／Discord）する。それ以外は通常のAIエラー文言を返す。
    """
    from shared.errors import get as err
    from shared.notify import notify_admin

    if is_credit_error(e):
        notify_admin(
            f"[{project_name}] Anthropicクレジット残高不足",
            f"{project_name} でAI呼び出し時にクレジット残高不足エラーが発生しました。\n"
            f"Anthropicの Plans & Billing でクレジットを追加してください。\n\n詳細: {e}",
        )
        return err("service_paused")
    return err("ai_error")
