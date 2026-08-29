import sys
import os
import re
import logging
from datetime import datetime, timezone, timedelta
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify
from notion_client import Client
from apscheduler.schedulers.background import BackgroundScheduler
import generator
import engagement
import notifier

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.errors import get as err
from shared.utils import handle_ai_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
bp = Blueprint("sns_management_hub", __name__, template_folder="templates", static_folder="static")
engagement.init()

_notion = None
def get_notion():
    global _notion
    if _notion is None and os.environ.get("NOTION_TOKEN"):
        _notion = Client(auth=os.environ["NOTION_TOKEN"])
    return _notion


def get_db_id():
    return os.environ.get("NOTION_DATABASE_ID", "")


SNS_TYPES = list(generator.SNS_HASHTAG_RULES.keys())
TONES = ["カジュアル・親しみやすい", "丁寧・プロフェッショナル", "テンション高め・エネルギッシュ"]


# ── Twitter投稿 ──────────────────────────────────────────────────────
def _twitter_client():
    required = ("TWITTER_API_KEY", "TWITTER_API_SECRET", "TWITTER_ACCESS_TOKEN", "TWITTER_ACCESS_TOKEN_SECRET")
    if not all(os.environ.get(k) for k in required):
        return None
    import tweepy
    return tweepy.Client(
        consumer_key=os.environ["TWITTER_API_KEY"],
        consumer_secret=os.environ["TWITTER_API_SECRET"],
        access_token=os.environ["TWITTER_ACCESS_TOKEN"],
        access_token_secret=os.environ["TWITTER_ACCESS_TOKEN_SECRET"],
    )


_URL_PATTERN = re.compile(r"https?://\S+")


def _strip_links(text: str) -> str:
    return _URL_PATTERN.sub("", text).strip()


def _post_tweet_with_optional_link_reply(client, content: str, url: str = "") -> str:
    """本文をリンクなしで投稿し、urlがあればリプライでURLのみ投稿する。

    Note記事などへの誘導は本文にリンクを置かず、リプライでURLを案内する方が
    インプレッションが落ちにくいというSNS運用上の方針による。
    """
    main_text = _strip_links(content) if url else content
    main_tweet = client.create_tweet(text=main_text)
    main_tweet_id = main_tweet.data["id"]
    if url:
        client.create_tweet(text=url, in_reply_to_tweet_id=main_tweet_id)
    return main_tweet_id


# ── 予約投稿スケジューラー ────────────────────────────────────────────
def check_scheduled_posts():
    notion, db_id = get_notion(), get_db_id()
    if not notion or not db_id:
        return
    try:
        now = datetime.now(timezone.utc).isoformat()
        res = notion.databases.query(
            database_id=db_id,
            filter={"and": [
                {"property": "状態",    "select": {"equals": "承認済み"}},
                {"property": "投稿日時", "date":   {"on_or_before": now}}
            ]}
        )
        for page in res["results"]:
            props   = page["properties"]
            title   = props["名前"]["title"][0]["plain_text"] if props["名前"]["title"] else "無題"
            content = props["投稿文"]["rich_text"][0]["plain_text"] if props["投稿文"]["rich_text"] else ""
            sns     = props["SNS種別"]["select"]["name"] if props["SNS種別"]["select"] else ""
            link_url = (props.get("URL", {}) or {}).get("url") or ""

            if sns == "LINE":
                if notifier.send_discord(f"[予約投稿] {title}", content):
                    generator.update_status(notion, page["id"], "投稿済み")
                    logger.info("予約投稿完了: %s (%s)", title, sns)
            elif sns == "Twitter":
                client = _twitter_client()
                if client:
                    _post_tweet_with_optional_link_reply(client, content, link_url)
                    generator.update_status(notion, page["id"], "投稿済み")
                    logger.info("予約投稿完了: %s (%s)", title, sns)
                else:
                    notifier.send_discord(f"[手動投稿が必要] {title}", content)
            else:  # Instagram など自動投稿API未対応
                notifier.send_discord(f"[手動投稿が必要] {title}", content)
    except Exception:
        logger.exception("予約投稿チェックでエラーが発生しました")


def check_reminder():
    notion, db_id = get_notion(), get_db_id()
    if not notion or not db_id:
        return
    try:
        now = datetime.now(timezone.utc)
        lo  = (now + timedelta(minutes=13)).isoformat()
        hi  = (now + timedelta(minutes=15)).isoformat()
        res = notion.databases.query(
            database_id=db_id,
            filter={"and": [
                {"property": "状態",    "select": {"equals": "承認済み"}},
                {"property": "投稿日時", "date":   {"on_or_after":  lo}},
                {"property": "投稿日時", "date":   {"on_or_before": hi}}
            ]}
        )
        for page in res["results"]:
            props   = page["properties"]
            title   = props["名前"]["title"][0]["plain_text"] if props["名前"]["title"] else "無題"
            content = props["投稿文"]["rich_text"][0]["plain_text"] if props["投稿文"]["rich_text"] else ""
            sched   = (props.get("投稿日時", {}).get("date") or {}).get("start", "")
            notifier.send_discord(
                f"⏰ 15分後に投稿予定: {title}",
                f"**投稿日時:** {sched[:16]}\n\n{content[:200]}",
                color=16776960
            )
    except Exception:
        logger.exception("リマインダーチェックでエラーが発生しました")


scheduler = BackgroundScheduler()
scheduler.add_job(check_scheduled_posts, "interval", minutes=1)
scheduler.add_job(check_reminder,        "interval", minutes=1)
scheduler.start()


# ── ルート ───────────────────────────────────────────────────────────
@bp.route("/")
def index():
    return render_template("sns_management_hub/index.html", sns_types=SNS_TYPES, tones=TONES)


@bp.route("/suggest", methods=["POST"])
def suggest():
    industry = request.form.get("industry", "").strip()
    target   = request.form.get("target",   "").strip()
    if not industry or not target:
        return jsonify({"ok": False, "error": "業界とターゲットを入力してください"}), 400
    if len(industry) > 100 or len(target) > 100:
        return jsonify({"ok": False, "error": "入力が長すぎます（100文字以内）"}), 400
    try:
        count = max(1, min(int(request.form.get("count", 15)), 50))
    except ValueError:
        count = 15
    try:
        topics = generator.suggest_topics(industry, target, count)
        hot    = engagement.hot_topics()
        return jsonify({"ok": True, "topics": topics, "hot": list(hot)})
    except Exception as e:
        logger.exception("suggest failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "sns-management-hub")}), 500


@bp.route("/hashtags", methods=["POST"])
def hashtags():
    topic    = request.form.get("topic", "").strip()
    sns_type = request.form.get("sns_type", "Instagram")
    industry = request.form.get("industry", "").strip()
    if not topic:
        return jsonify({"ok": False, "error": "テーマを入力してください"}), 400
    if len(topic) > 200:
        return jsonify({"ok": False, "error": "200文字以内で入力してください"}), 400
    if sns_type not in SNS_TYPES:
        sns_type = "Instagram"
    try:
        data = generator.generate_hashtags(topic, sns_type, industry)
        return jsonify({"ok": True, **data})
    except Exception as e:
        logger.exception("hashtags failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "sns-management-hub")}), 500


@bp.route("/variations", methods=["POST"])
def variations():
    topic    = request.form.get("topic", "").strip()
    sns_type = request.form.get("sns_type", "Instagram")
    tone     = request.form.get("tone", TONES[0])
    if not topic:
        return jsonify({"ok": False, "error": "テーマを入力してください"}), 400
    if len(topic) > 200:
        return jsonify({"ok": False, "error": "200文字以内で入力してください"}), 400
    if sns_type not in SNS_TYPES:
        sns_type = "Instagram"
    if tone not in TONES:
        tone = TONES[0]
    try:
        data = generator.generate_variations(topic, sns_type, tone)
        return jsonify({"ok": True, "variations": data})
    except Exception as e:
        logger.exception("variations failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "sns-management-hub")}), 500


@bp.route("/image_prompt", methods=["POST"])
def image_prompt():
    post_text = request.form.get("post_text", "").strip()
    sns_type  = request.form.get("sns_type", "Instagram")
    if not post_text:
        return jsonify({"ok": False, "error": "投稿文を選択してください"}), 400
    if len(post_text) > 5000:
        return jsonify({"ok": False, "error": "入力が長すぎます"}), 400
    if sns_type not in SNS_TYPES:
        sns_type = "Instagram"
    try:
        prompt = generator.generate_image_prompt(post_text, sns_type)
        return jsonify({"ok": True, "image_prompt": prompt})
    except Exception as e:
        logger.exception("image_prompt failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "sns-management-hub")}), 500


@bp.route("/save_to_calendar", methods=["POST"])
def save_to_calendar():
    topic     = request.form.get("topic", "").strip()
    sns_type  = request.form.get("sns_type", "Instagram")
    post_text = request.form.get("post_text", "").strip()
    hashtags  = request.form.get("hashtags", "").strip()
    scheduled_at = request.form.get("scheduled_at", "").strip()
    link_url  = request.form.get("url", "").strip()

    if not post_text:
        return jsonify({"ok": False, "error": "投稿内容を選択してください"}), 400
    if len(post_text) > 5000 or len(hashtags) > 1000:
        return jsonify({"ok": False, "error": "入力が長すぎます"}), 400
    if sns_type not in SNS_TYPES:
        sns_type = "Instagram"

    if hashtags:
        post_text = f"{post_text}\n\n{hashtags}"

    notion, db_id = get_notion(), get_db_id()
    if not notion or not db_id:
        return jsonify({"ok": False, "error": "Notion未設定のため保存できません"}), 503

    title = (topic or post_text)[:50]
    try:
        page_id = generator.save_to_calendar(
            notion, db_id, title, sns_type, post_text, scheduled_at or None, link_url or None
        )
        return jsonify({"ok": True, "page_id": page_id})
    except Exception:
        logger.exception("save_to_calendar failed")
        return jsonify({"ok": False, "error": "投稿カレンダーへの保存に失敗しました"}), 500


@bp.route("/calendar")
def calendar():
    notion, db_id = get_notion(), get_db_id()
    if not notion or not db_id:
        return jsonify({"ok": True, "posts": [], "warning": "Notion未設定"})
    posts = generator.fetch_calendar(notion, db_id)
    return jsonify({"ok": True, "posts": posts})


@bp.route("/posts")
def posts():
    notion, db_id = get_notion(), get_db_id()
    if not notion or not db_id:
        return jsonify({"ok": True, "posts": [], "warning": "Notion未設定"})
    return jsonify({"ok": True, "posts": generator.fetch_all_posts(notion, db_id)})


@bp.route("/approve/<page_id>", methods=["POST"])
def approve(page_id):
    notion = get_notion()
    if not notion:
        return jsonify({"ok": False, "error": err("missing_notion")}), 503
    try:
        generator.update_status(notion, page_id, "承認済み")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/schedule_post/<page_id>", methods=["POST"])
def schedule_post(page_id):
    notion = get_notion()
    if not notion:
        return jsonify({"ok": False, "error": err("missing_notion")}), 503
    scheduled_at = request.form.get("scheduled_at")
    link_url = request.form.get("url")
    try:
        generator.update_schedule(notion, page_id, scheduled_at, url=link_url)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/edit_schedule/<page_id>", methods=["POST"])
def edit_schedule(page_id):
    notion = get_notion()
    if not notion:
        return jsonify({"ok": False, "error": err("missing_notion")}), 503
    new_time    = request.form.get("scheduled_at")
    new_content = request.form.get("content")
    new_url     = request.form.get("url")
    try:
        generator.edit_post(notion, page_id, new_time, new_content, url=new_url)
        return jsonify({"ok": True, "char_count": len(new_content) if new_content else 0})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/cancel_schedule/<page_id>", methods=["POST"])
def cancel_schedule(page_id):
    notion = get_notion()
    if not notion:
        return jsonify({"ok": False, "error": err("missing_notion")}), 503
    try:
        generator.cancel_schedule(notion, page_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/post_discord/<page_id>", methods=["POST"])
def post_discord_route(page_id):
    notion = get_notion()
    if not notion:
        return jsonify({"ok": False, "error": err("missing_notion")}), 503
    try:
        page    = notion.pages.retrieve(page_id=page_id)
        props   = page["properties"]
        title   = props["名前"]["title"][0]["plain_text"] if props["名前"]["title"] else "無題"
        content = props["投稿文"]["rich_text"][0]["plain_text"] if props["投稿文"]["rich_text"] else ""
        if notifier.send_discord(title, content):
            generator.update_status(notion, page_id, "投稿済み")
            return jsonify({"ok": True})
        return jsonify({"ok": False, "error": err("missing_discord")}), 500
    except Exception as e:
        return jsonify({"ok": False, "error": err("ai_error", str(e))}), 500


@bp.route("/post_twitter/<page_id>", methods=["POST"])
def post_twitter(page_id):
    notion = get_notion()
    if not notion:
        return jsonify({"ok": False, "error": err("missing_notion")}), 503
    client = _twitter_client()
    if not client:
        return jsonify({"ok": False, "error": err("missing_twitter")}), 503
    try:
        page     = notion.pages.retrieve(page_id=page_id)
        content  = page["properties"]["投稿文"]["rich_text"][0]["plain_text"]
        link_url = (page["properties"].get("URL", {}) or {}).get("url") or ""
        _post_tweet_with_optional_link_reply(client, content, link_url)
        generator.update_status(notion, page_id, "投稿済み")
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/delete/<page_id>", methods=["POST"])
def delete(page_id):
    notion = get_notion()
    if not notion:
        return jsonify({"ok": False, "error": err("missing_notion")}), 503
    try:
        generator.delete_post(notion, page_id)
        return jsonify({"ok": True})
    except Exception as e:
        return jsonify({"ok": False, "error": str(e)}), 500


@bp.route("/engage", methods=["POST"])
def engage():
    topic    = request.form.get("topic",    "").strip()
    sns_type = request.form.get("sns_type", "").strip()
    if not topic or sns_type not in SNS_TYPES:
        return jsonify({"ok": False, "error": "トピックとSNS種別を入力してください"}), 400
    try:
        likes    = max(0, int(request.form.get("likes",    0)))
        comments = max(0, int(request.form.get("comments", 0)))
        reach    = max(0, int(request.form.get("reach",    0)))
    except ValueError:
        return jsonify({"ok": False, "error": err("invalid_input")}), 400
    engagement.record(topic, sns_type, likes, comments, reach)
    return jsonify({"ok": True})


@bp.route("/analytics")
def analytics():
    return jsonify({"ok": True, "data": engagement.top_topics()})


@bp.route("/hashtag_ranking")
def hashtag_ranking():
    notion, db_id = get_notion(), get_db_id()
    if not notion or not db_id:
        return jsonify({"ok": True, "ranking": []})
    counts = {}
    for p in generator.fetch_all_posts(notion, db_id):
        for tag in re.findall(r"#\S+", p["content"]):
            counts[tag] = counts.get(tag, 0) + 1
    ranked = sorted(counts.items(), key=lambda x: -x[1])[:30]
    return jsonify({"ok": True, "ranking": ranked})


def create_app():
    app = Flask(__name__)
    init_csrf(app)
    app.register_blueprint(bp)
    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5015)
