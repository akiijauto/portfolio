import sys
import os
import datetime
import logging
from pathlib import Path
import anthropic

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.utils import call_claude_json, call_claude_text

logger = logging.getLogger(__name__)

SNS_HASHTAG_RULES = {
    "Instagram": {"max": 30, "note": "人気タグ・ニッチタグ・ブランドタグをバランスよく"},
    "Twitter":   {"max": 5,  "note": "2〜5個、検索に引っかかる具体的なタグのみ"},
    "LINE":      {"max": 2,  "note": "LINEはタグ文化が薄い。0〜2個、絵文字代わり程度"},
}

VARIATION_ANGLES = [
    ("問題提起型", "読者の悩みや痛みを冒頭に置き、共感から入る"),
    ("メリット提示型", "得られる価値・ベネフィットを冒頭で明確に伝える"),
    ("ストーリー型", "「〜してみたら」「実は先週」などの体験談風の書き出し"),
]


def _client() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])


def _create_json(prompt: str, max_tokens: int, retries: int = 2):
    """AIにJSON形式の応答を生成させ、パースして返す。"""
    return call_claude_json(_client(), "claude-haiku-4-5-20251001", max_tokens, prompt, max_retries=retries)


def generate_hashtags(topic: str, sns_type: str, industry: str = "") -> dict:
    rule = SNS_HASHTAG_RULES.get(sns_type, SNS_HASHTAG_RULES["Instagram"])
    ind_note = f"業界・ジャンル: {industry}" if industry.strip() else ""

    prompt = f"""以下の条件でSNSのハッシュタグセットを生成してください。

テーマ: {topic}
SNS: {sns_type}
ルール: {rule['note']}（最大{rule['max']}個）
{ind_note}

以下のJSON形式で返してください（説明不要、JSONのみ）:
{{
  "hashtags": ["#タグ1", "#タグ2", ...],
  "strategy": "このハッシュタグ選定の戦略を1〜2文で説明"
}}

{sns_type}に最適な{rule['max']}個以内で、日本語タグと英語タグを混在させてください。"""

    return _create_json(prompt, max_tokens=1024)


def generate_variations(topic: str, sns_type: str, tone: str) -> list[dict]:
    angles_text = "\n".join(
        f"{i+1}. {name}: {desc}" for i, (name, desc) in enumerate(VARIATION_ANGLES)
    )
    char_limit = {"Instagram": 2200, "Twitter": 140, "LINE": 500}.get(sns_type, 500)

    prompt = f"""テーマ「{topic}」の{sns_type}投稿文を、以下の3つの切り口でそれぞれ作成してください。

切り口:
{angles_text}

条件:
- 文体: {tone}
- 文字数: 各{char_limit}文字以内
- 改行・絵文字を適度に使いSNSらしい見た目に

以下のJSON形式で返してください（JSONのみ）:
[
  {{"angle": "問題提起型", "post": "投稿文1"}},
  {{"angle": "メリット提示型", "post": "投稿文2"}},
  {{"angle": "ストーリー型", "post": "投稿文3"}}
]"""

    # Instagramは1投稿2200文字まで許容するため、3案分の絵文字混じり日本語JSONは
    # 4000トークン超になることがある(以前のmax_tokens=1500ではUnterminated stringで失敗していた)
    return _create_json(prompt, max_tokens=8192)


def suggest_topics(industry: str, target: str, count: int = 15) -> list[str]:
    """業界・ターゲットに合う投稿テーマをAIに提案させる。"""
    prompt = (
        f"SNS運用担当者として、以下の条件に合う投稿テーマを{count}個提案してください。\n\n"
        f"業界: {industry}\nターゲット: {target}\n\n"
        f"JSON配列のみ出力（日本語・テーマのみ）：\n"
        f'["テーマ1", "テーマ2", ...]'
    )
    return call_claude_json(_client(), "claude-haiku-4-5-20251001", 2048, prompt)


def generate_image_prompt(post_text: str, sns_type: str) -> str:
    """選択済みの投稿文に合わせた画像生成プロンプト(英語)を作成する。"""
    prompt = (
        f"以下の{sns_type}投稿文に合う画像を生成するための、Midjourney/DALL-E向けの"
        f"英語の画像プロンプトを1つ作成してください。50words以内。\n\n"
        f"投稿文:\n{post_text}\n\n"
        f"出力は画像プロンプトの英文のみ。説明・補足・引用符は不要です。"
    )
    return call_claude_text(_client(), "claude-haiku-4-5-20251001", 256, prompt)


def save_to_calendar(notion_client, database_id: str, title: str, sns_type: str,
                      post_text: str, scheduled_at: str | None = None,
                      url: str | None = None) -> str:
    """選択したバリエーション投稿文＋ハッシュタグをNotionの投稿カレンダーDBに保存する。

    urlを指定すると、本文からリンクを除いた投稿＋リプライでURLを案内する
    投稿フローの対象になる（post_twitter/check_scheduled_posts側で処理）。
    """
    props = {
        "名前":   {"title":     [{"text": {"content": title}}]},
        "SNS種別": {"select":   {"name": sns_type}},
        "投稿文":  {"rich_text": [{"text": {"content": post_text}}]},
        "状態":   {"select":    {"name": "下書き"}},
        "作成日":  {"date":     {"start": datetime.date.today().isoformat()}},
    }
    if scheduled_at:
        props["投稿日時"] = {"date": {"start": scheduled_at}}
    if url:
        props["URL"] = {"url": url}

    page = notion_client.pages.create(
        parent={"database_id": database_id},
        properties=props,
    )
    return page["id"]


def fetch_calendar(notion_client, database_id: str) -> list[dict]:
    """Notion DB から今後の予約投稿を取得してカレンダー用データに変換。"""
    try:
        result = notion_client.databases.query(
            database_id=database_id,
            filter={"property": "状態", "select": {"does_not_equal": "投稿済み"}},
            sorts=[{"property": "投稿日時", "direction": "ascending"}],
            page_size=50,
        )
    except Exception as e:
        logger.warning("Notion fetch failed: %s", e)
        return []

    posts = []
    for page in result.get("results", []):
        props = page.get("properties", {})

        title_arr = props.get("名前", {}).get("title", [])
        title = title_arr[0]["text"]["content"] if title_arr else "(無題)"

        sns = props.get("SNS種別", {}).get("select") or {}
        status = props.get("状態", {}).get("select") or {}
        dt_obj = props.get("投稿日時", {}).get("date") or {}
        scheduled = dt_obj.get("start", "")

        posts.append({
            "id": page["id"],
            "title": title,
            "sns": sns.get("name", ""),
            "status": status.get("name", ""),
            "scheduled": scheduled,
            "url": page.get("url", ""),
            "link_url": props.get("URL", {}).get("url") or "",
        })
    return posts


def fetch_all_posts(notion_client, database_id: str) -> list[dict]:
    """状態を問わず全件取得する(カレンダー一覧・ハッシュタグ集計・予約投稿チェック用)。"""
    posts, cursor = [], None
    while True:
        kwargs = {
            "database_id": database_id,
            "sorts": [{"property": "作成日", "direction": "descending"}],
            "page_size": 100,
        }
        if cursor:
            kwargs["start_cursor"] = cursor
        response = notion_client.databases.query(**kwargs)
        for page in response["results"]:
            props = page["properties"]

            title_arr = props.get("名前", {}).get("title", [])
            title = title_arr[0]["plain_text"] if title_arr else "(無題)"

            content_arr = props.get("投稿文", {}).get("rich_text", [])
            content = content_arr[0]["plain_text"] if content_arr else ""

            sns = props.get("SNS種別", {}).get("select") or {}
            status = props.get("状態", {}).get("select") or {}
            created = props.get("作成日", {}).get("date") or {}
            scheduled = (props.get("投稿日時", {}).get("date") or {}).get("start", "")

            posts.append({
                "id": page["id"],
                "title": title,
                "sns": sns.get("name", ""),
                "content": content,
                "char_count": len(content),
                "status": status.get("name", ""),
                "date": created.get("start", ""),
                "scheduled": scheduled[:16].replace("T", " ") if scheduled else "",
                "sched_raw": scheduled[:16] if scheduled else "",
                "url": page.get("url", ""),
                "link_url": props.get("URL", {}).get("url") or "",
            })
        if not response.get("has_more"):
            break
        cursor = response.get("next_cursor")
    return posts


def update_status(notion_client, page_id: str, status: str) -> None:
    """投稿の状態(下書き/承認済み/投稿済み)を更新する。"""
    notion_client.pages.update(page_id=page_id, properties={"状態": {"select": {"name": status}}})


def update_schedule(notion_client, page_id: str, scheduled_at: str | None = None,
                     content: str | None = None, url: str | None = None) -> None:
    """投稿日時・本文を更新する(承認済みにする)。"""
    props = {"状態": {"select": {"name": "承認済み"}}}
    if scheduled_at:
        props["投稿日時"] = {"date": {"start": scheduled_at}}
    if content is not None:
        props["投稿文"] = {"rich_text": [{"text": {"content": content}}]}
    if url is not None:
        props["URL"] = {"url": url or None}
    notion_client.pages.update(page_id=page_id, properties=props)


def edit_post(notion_client, page_id: str, scheduled_at: str | None = None,
              content: str | None = None, url: str | None = None) -> None:
    """予約日時・本文・URLのみを編集する(状態は変更しない)。"""
    props = {}
    if scheduled_at:
        props["投稿日時"] = {"date": {"start": scheduled_at}}
    if content is not None:
        props["投稿文"] = {"rich_text": [{"text": {"content": content}}]}
    if url is not None:
        props["URL"] = {"url": url or None}
    if props:
        notion_client.pages.update(page_id=page_id, properties=props)


def cancel_schedule(notion_client, page_id: str) -> None:
    """予約を取り消して下書きに戻す。"""
    notion_client.pages.update(page_id=page_id, properties={
        "状態": {"select": {"name": "下書き"}},
        "投稿日時": {"date": None},
    })


def delete_post(notion_client, page_id: str) -> None:
    """投稿をアーカイブ(削除)する。"""
    notion_client.pages.update(page_id=page_id, archived=True)
