"""15_sns_management_hub のテスト（app.py エンドポイント + generator.py ロジック）。"""
import json
import os
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parents[3]
PROJECT = ROOT / "projects" / "15_sns_management_hub"

sys.path.insert(0, str(PROJECT))
for _mod in ("generator", "app"):
    sys.modules.pop(_mod, None)

spec = importlib.util.spec_from_file_location("sns_app", PROJECT / "app.py")
sns_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sns_app_module)

flask_app = sns_app_module.app
generator = sns_app_module.generator
flask_app.root_path = str(PROJECT)
flask_app.template_folder = str(PROJECT / "templates")
flask_app.static_folder = str(PROJECT / "static")


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.test_client() as c:
        yield c


# ── / ────────────────────────────────────────────────────────────

class TestIndex:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# ── /suggest ─────────────────────────────────────────────────────

class TestSuggestEndpoint:
    def test_missing_industry_returns_400(self, client):
        resp = client.post("/suggest", data={"target": "20代女性"})
        assert resp.status_code == 400

    def test_missing_target_returns_400(self, client):
        resp = client.post("/suggest", data={"industry": "カフェ"})
        assert resp.status_code == 400

    def test_too_long_input_returns_400(self, client):
        resp = client.post("/suggest", data={"industry": "a" * 101, "target": "20代女性"})
        assert resp.status_code == 400

    def test_success_returns_topics_and_hot(self, client):
        with patch.object(generator, "suggest_topics", return_value=["テーマ1", "テーマ2"]), \
             patch.object(sns_app_module.engagement, "hot_topics", return_value={"テーマ1"}):
            resp = client.post("/suggest", data={"industry": "カフェ", "target": "20代女性"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["topics"] == ["テーマ1", "テーマ2"]
        assert data["hot"] == ["テーマ1"]

    def test_invalid_count_falls_back_to_default(self, client):
        with patch.object(generator, "suggest_topics", return_value=[]) as mock_suggest, \
             patch.object(sns_app_module.engagement, "hot_topics", return_value=set()):
            resp = client.post("/suggest", data={"industry": "カフェ", "target": "20代女性", "count": "abc"})
        assert resp.status_code == 200
        args, _ = mock_suggest.call_args
        assert args[2] == 15

    def test_generation_error_returns_500(self, client):
        with patch.object(generator, "suggest_topics", side_effect=Exception("boom")):
            resp = client.post("/suggest", data={"industry": "カフェ", "target": "20代女性"})
        assert resp.status_code == 500


# ── /image_prompt ────────────────────────────────────────────────

class TestImagePromptEndpoint:
    def test_empty_post_text_returns_400(self, client):
        resp = client.post("/image_prompt", data={"post_text": ""})
        assert resp.status_code == 400

    def test_too_long_input_returns_400(self, client):
        resp = client.post("/image_prompt", data={"post_text": "a" * 5001})
        assert resp.status_code == 400

    def test_success_returns_image_prompt(self, client):
        with patch.object(generator, "generate_image_prompt", return_value="A cozy cafe scene"):
            resp = client.post("/image_prompt", data={"post_text": "投稿文", "sns_type": "Instagram"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["image_prompt"] == "A cozy cafe scene"

    def test_generation_error_returns_500(self, client):
        with patch.object(generator, "generate_image_prompt", side_effect=Exception("boom")):
            resp = client.post("/image_prompt", data={"post_text": "投稿文"})
        assert resp.status_code == 500


# ── /posts ───────────────────────────────────────────────────────

class TestPostsEndpoint:
    def test_notion_unconfigured_returns_warning(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=None):
            resp = client.get("/posts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["posts"] == []
        assert data["warning"] == "Notion未設定"

    def test_configured_returns_posts(self, client):
        sample_posts = [{"id": "page1", "title": "投稿A", "sns": "Instagram", "status": "下書き"}]
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.dict(os.environ, {"NOTION_DATABASE_ID": "db123"}), \
             patch.object(generator, "fetch_all_posts", return_value=sample_posts):
            resp = client.get("/posts")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["posts"] == sample_posts


# ── /approve, /schedule_post, /edit_schedule, /cancel_schedule, /delete ──

class TestPostManagementEndpoints:
    def test_approve_notion_unconfigured_returns_503(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=None):
            resp = client.post("/approve/page1")
        assert resp.status_code == 503

    def test_approve_success(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.object(generator, "update_status") as mock_update:
            resp = client.post("/approve/page1")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        args, _ = mock_update.call_args
        assert args[1] == "page1"
        assert args[2] == "承認済み"

    def test_schedule_post_success(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.object(generator, "update_schedule") as mock_update:
            resp = client.post("/schedule_post/page1", data={"scheduled_at": "2026-06-20T10:00:00"})
        assert resp.status_code == 200
        args, _ = mock_update.call_args
        assert args[1] == "page1"
        assert args[2] == "2026-06-20T10:00:00"

    def test_edit_schedule_success(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.object(generator, "edit_post") as mock_edit:
            resp = client.post("/edit_schedule/page1", data={"scheduled_at": "2026-06-20T10:00:00", "content": "新しい本文"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["char_count"] == len("新しい本文")
        mock_edit.assert_called_once()

    def test_cancel_schedule_success(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.object(generator, "cancel_schedule") as mock_cancel:
            resp = client.post("/cancel_schedule/page1")
        assert resp.status_code == 200
        mock_cancel.assert_called_once()

    def test_delete_success(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.object(generator, "delete_post") as mock_delete:
            resp = client.post("/delete/page1")
        assert resp.status_code == 200
        mock_delete.assert_called_once()


# ── /post_discord, /post_twitter ────────────────────────────────

class TestPostDiscordEndpoint:
    def test_notion_unconfigured_returns_503(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=None):
            resp = client.post("/post_discord/page1")
        assert resp.status_code == 503

    def test_success_marks_posted(self, client):
        mock_notion = MagicMock()
        mock_notion.pages.retrieve.return_value = {
            "properties": {
                "名前": {"title": [{"plain_text": "投稿A"}]},
                "投稿文": {"rich_text": [{"plain_text": "本文"}]},
            }
        }
        with patch.object(sns_app_module, "get_notion", return_value=mock_notion), \
             patch.object(sns_app_module.notifier, "send_discord", return_value=True), \
             patch.object(generator, "update_status") as mock_update:
            resp = client.post("/post_discord/page1")
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        args, _ = mock_update.call_args
        assert args[2] == "投稿済み"

    def test_discord_failure_returns_500(self, client):
        mock_notion = MagicMock()
        mock_notion.pages.retrieve.return_value = {
            "properties": {
                "名前": {"title": [{"plain_text": "投稿A"}]},
                "投稿文": {"rich_text": [{"plain_text": "本文"}]},
            }
        }
        with patch.object(sns_app_module, "get_notion", return_value=mock_notion), \
             patch.object(sns_app_module.notifier, "send_discord", return_value=False):
            resp = client.post("/post_discord/page1")
        assert resp.status_code == 500


class TestPostTwitterEndpoint:
    def test_notion_unconfigured_returns_503(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=None):
            resp = client.post("/post_twitter/page1")
        assert resp.status_code == 503

    def test_missing_credentials_returns_503(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.object(sns_app_module, "_twitter_client", return_value=None):
            resp = client.post("/post_twitter/page1")
        assert resp.status_code == 503

    def test_success_marks_posted(self, client):
        mock_notion = MagicMock()
        mock_notion.pages.retrieve.return_value = {
            "properties": {"投稿文": {"rich_text": [{"plain_text": "本文"}]}}
        }
        mock_twitter = MagicMock()
        with patch.object(sns_app_module, "get_notion", return_value=mock_notion), \
             patch.object(sns_app_module, "_twitter_client", return_value=mock_twitter), \
             patch.object(generator, "update_status") as mock_update:
            resp = client.post("/post_twitter/page1")
        assert resp.status_code == 200
        mock_twitter.create_tweet.assert_called_once_with(text="本文")
        args, _ = mock_update.call_args
        assert args[2] == "投稿済み"


# ── /engage, /analytics, /hashtag_ranking ───────────────────────

class TestEngageEndpoint:
    def test_missing_topic_returns_400(self, client):
        resp = client.post("/engage", data={"sns_type": "Instagram"})
        assert resp.status_code == 400

    def test_invalid_sns_type_returns_400(self, client):
        resp = client.post("/engage", data={"topic": "テーマ", "sns_type": "TikTok"})
        assert resp.status_code == 400

    def test_invalid_numbers_returns_400(self, client):
        resp = client.post("/engage", data={"topic": "テーマ", "sns_type": "Instagram", "likes": "abc"})
        assert resp.status_code == 400

    def test_success_records_engagement(self, client):
        with patch.object(sns_app_module.engagement, "record") as mock_record:
            resp = client.post("/engage", data={
                "topic": "テーマ", "sns_type": "Instagram", "likes": "10", "comments": "2", "reach": "100",
            })
        assert resp.status_code == 200
        assert resp.get_json()["ok"] is True
        mock_record.assert_called_once_with("テーマ", "Instagram", 10, 2, 100)


class TestAnalyticsEndpoint:
    def test_returns_top_topics(self, client):
        sample = [{"topic": "テーマ", "sns_type": "Instagram", "count": 3}]
        with patch.object(sns_app_module.engagement, "top_topics", return_value=sample):
            resp = client.get("/analytics")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["data"] == sample


class TestHashtagRankingEndpoint:
    def test_notion_unconfigured_returns_empty(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=None):
            resp = client.get("/hashtag_ranking")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["ranking"] == []

    def test_counts_hashtags_from_posts(self, client):
        sample_posts = [
            {"content": "投稿文 #カフェ #朝活"},
            {"content": "別の投稿 #カフェ"},
        ]
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.dict(os.environ, {"NOTION_DATABASE_ID": "db123"}), \
             patch.object(generator, "fetch_all_posts", return_value=sample_posts):
            resp = client.get("/hashtag_ranking")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ranking"][0] == ["#カフェ", 2]


# ── /hashtags ────────────────────────────────────────────────────

class TestHashtagsEndpoint:
    def test_empty_topic_returns_400(self, client):
        resp = client.post("/hashtags", data={"topic": ""})
        assert resp.status_code == 400

    def test_too_long_topic_returns_400(self, client):
        resp = client.post("/hashtags", data={"topic": "a" * 201})
        assert resp.status_code == 400

    def test_invalid_sns_type_falls_back_to_instagram(self, client):
        result = {"hashtags": ["#tag1"], "strategy": "戦略説明"}
        with patch.object(generator, "generate_hashtags", return_value=result) as mock_gen:
            resp = client.post("/hashtags", data={"topic": "テスト", "sns_type": "TikTok"})
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[1] == "Instagram"

    def test_success_returns_hashtags(self, client):
        result = {"hashtags": ["#tag1", "#tag2"], "strategy": "戦略説明"}
        with patch.object(generator, "generate_hashtags", return_value=result):
            resp = client.post("/hashtags", data={"topic": "テスト", "sns_type": "Twitter"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["hashtags"] == ["#tag1", "#tag2"]

    def test_generation_error_returns_500(self, client):
        with patch.object(generator, "generate_hashtags", side_effect=Exception("boom")):
            resp = client.post("/hashtags", data={"topic": "テスト"})
        assert resp.status_code == 500


# ── /variations ──────────────────────────────────────────────────

class TestVariationsEndpoint:
    def test_empty_topic_returns_400(self, client):
        resp = client.post("/variations", data={"topic": ""})
        assert resp.status_code == 400

    def test_too_long_topic_returns_400(self, client):
        resp = client.post("/variations", data={"topic": "a" * 201})
        assert resp.status_code == 400

    def test_invalid_sns_type_falls_back_to_instagram(self, client):
        result = [{"angle": "問題提起型", "post": "投稿文"}]
        with patch.object(generator, "generate_variations", return_value=result) as mock_gen:
            resp = client.post("/variations", data={"topic": "テスト", "sns_type": "TikTok"})
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[1] == "Instagram"

    def test_invalid_tone_falls_back_to_default(self, client):
        result = [{"angle": "問題提起型", "post": "投稿文"}]
        with patch.object(generator, "generate_variations", return_value=result) as mock_gen:
            resp = client.post("/variations", data={"topic": "テスト", "tone": "存在しないトーン"})
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[2] == sns_app_module.TONES[0]

    def test_success_returns_variations(self, client):
        result = [
            {"angle": "問題提起型", "post": "投稿文1"},
            {"angle": "メリット提示型", "post": "投稿文2"},
            {"angle": "ストーリー型", "post": "投稿文3"},
        ]
        with patch.object(generator, "generate_variations", return_value=result):
            resp = client.post("/variations", data={"topic": "テスト"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["variations"] == result

    def test_generation_error_returns_500(self, client):
        with patch.object(generator, "generate_variations", side_effect=Exception("boom")):
            resp = client.post("/variations", data={"topic": "テスト"})
        assert resp.status_code == 500


# ── /calendar ────────────────────────────────────────────────────

class TestCalendarEndpoint:
    def test_notion_unconfigured_returns_warning(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=None):
            resp = client.get("/calendar")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["posts"] == []
        assert data["warning"] == "Notion未設定"

    def test_configured_returns_posts(self, client):
        sample_posts = [{
            "id": "page1", "title": "投稿A", "sns": "Instagram",
            "status": "予約済み", "scheduled": "2026-06-15T10:00:00", "url": "https://notion.so/page1",
        }]
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.dict(os.environ, {"NOTION_DATABASE_ID": "db123"}), \
             patch.object(generator, "fetch_calendar", return_value=sample_posts):
            resp = client.get("/calendar")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["posts"] == sample_posts


# ── /save_to_calendar ────────────────────────────────────────────

class TestSaveToCalendarEndpoint:
    def test_empty_post_text_returns_400(self, client):
        resp = client.post("/save_to_calendar", data={"post_text": ""})
        assert resp.status_code == 400

    def test_too_long_input_returns_400(self, client):
        resp = client.post("/save_to_calendar", data={"post_text": "a" * 5001})
        assert resp.status_code == 400

    def test_notion_unconfigured_returns_503(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=None):
            resp = client.post("/save_to_calendar", data={"post_text": "投稿文", "topic": "テーマ"})
        assert resp.status_code == 503

    def test_success_saves_and_returns_page_id(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.dict(os.environ, {"NOTION_DATABASE_ID": "db123"}), \
             patch.object(generator, "save_to_calendar", return_value="page123") as mock_save:
            resp = client.post("/save_to_calendar", data={
                "post_text": "投稿文", "topic": "テーマ", "sns_type": "Twitter",
                "hashtags": "#a #b", "scheduled_at": "2026-06-20T10:00:00",
            })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["page_id"] == "page123"
        args, _ = mock_save.call_args
        assert args[2] == "テーマ"
        assert args[3] == "Twitter"
        assert "投稿文" in args[4]
        assert "#a #b" in args[4]
        assert args[5] == "2026-06-20T10:00:00"

    def test_save_failure_returns_500(self, client):
        with patch.object(sns_app_module, "get_notion", return_value=MagicMock()), \
             patch.dict(os.environ, {"NOTION_DATABASE_ID": "db123"}), \
             patch.object(generator, "save_to_calendar", side_effect=Exception("boom")):
            resp = client.post("/save_to_calendar", data={"post_text": "投稿文"})
        assert resp.status_code == 500


# ── generator.save_to_calendar() ─────────────────────────────────

class TestSaveToCalendar:
    def test_creates_page_with_expected_properties(self):
        mock_notion = MagicMock()
        mock_notion.pages.create.return_value = {"id": "page123"}
        page_id = generator.save_to_calendar(mock_notion, "db123", "タイトル", "Instagram", "投稿文")
        assert page_id == "page123"
        kwargs = mock_notion.pages.create.call_args.kwargs
        assert kwargs["parent"] == {"database_id": "db123"}
        props = kwargs["properties"]
        assert props["名前"]["title"][0]["text"]["content"] == "タイトル"
        assert props["SNS種別"]["select"]["name"] == "Instagram"
        assert props["投稿文"]["rich_text"][0]["text"]["content"] == "投稿文"
        assert props["状態"]["select"]["name"] == "下書き"
        assert "投稿日時" not in props

    def test_includes_scheduled_at_when_provided(self):
        mock_notion = MagicMock()
        mock_notion.pages.create.return_value = {"id": "page123"}
        generator.save_to_calendar(mock_notion, "db123", "タイトル", "Instagram", "投稿文", "2026-06-20T10:00:00")
        props = mock_notion.pages.create.call_args.kwargs["properties"]
        assert props["投稿日時"]["date"]["start"] == "2026-06-20T10:00:00"


# ── generator.fetch_calendar() ──────────────────────────────────

class TestFetchCalendar:
    def test_parses_notion_pages(self):
        mock_notion = MagicMock()
        mock_notion.databases.query.return_value = {
            "results": [{
                "id": "page1",
                "url": "https://notion.so/page1",
                "properties": {
                    "名前": {"title": [{"text": {"content": "投稿A"}}]},
                    "SNS種別": {"select": {"name": "Instagram"}},
                    "状態": {"select": {"name": "予約済み"}},
                    "投稿日時": {"date": {"start": "2026-06-15T10:00:00"}},
                },
            }]
        }
        posts = generator.fetch_calendar(mock_notion, "db123")
        assert len(posts) == 1
        assert posts[0]["title"] == "投稿A"
        assert posts[0]["sns"] == "Instagram"
        assert posts[0]["status"] == "予約済み"
        assert posts[0]["scheduled"] == "2026-06-15T10:00:00"

    def test_no_title_returns_placeholder(self):
        mock_notion = MagicMock()
        mock_notion.databases.query.return_value = {
            "results": [{
                "id": "page1", "url": "",
                "properties": {"名前": {"title": []}},
            }]
        }
        posts = generator.fetch_calendar(mock_notion, "db123")
        assert posts[0]["title"] == "(無題)"

    def test_query_failure_returns_empty_list(self):
        mock_notion = MagicMock()
        mock_notion.databases.query.side_effect = Exception("API error")
        posts = generator.fetch_calendar(mock_notion, "db123")
        assert posts == []


# ── generator.suggest_topics() / generate_image_prompt() ────────

class TestSuggestTopics:
    def test_uses_correct_max_tokens_and_parses_json(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text='["テーマ1", "テーマ2"]')]
        )
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.suggest_topics("カフェ", "20代女性", count=2)
        assert result == ["テーマ1", "テーマ2"]
        assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 2048

    def test_retries_on_malformed_json(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            MagicMock(content=[MagicMock(text='["テーマ1"')]),
            MagicMock(content=[MagicMock(text='["テーマ1", "テーマ2"]')]),
        ]
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.suggest_topics("カフェ", "20代女性", count=2)
        assert result == ["テーマ1", "テーマ2"]
        assert mock_client.messages.create.call_count == 2


class TestGenerateImagePrompt:
    def test_returns_stripped_text(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = MagicMock(
            content=[MagicMock(text="  A cozy cafe scene  ")]
        )
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_image_prompt("投稿文", "Instagram")
        assert result == "A cozy cafe scene"
        assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 256


# ── generator.fetch_all_posts() / update系 ────────────────────────

class TestFetchAllPosts:
    def test_parses_all_posts_with_pagination(self):
        mock_notion = MagicMock()
        mock_notion.databases.query.side_effect = [
            {
                "results": [{
                    "id": "page1", "url": "https://notion.so/page1",
                    "properties": {
                        "名前": {"title": [{"plain_text": "投稿A"}]},
                        "SNS種別": {"select": {"name": "Instagram"}},
                        "投稿文": {"rich_text": [{"plain_text": "本文"}]},
                        "状態": {"select": {"name": "下書き"}},
                        "作成日": {"date": {"start": "2026-06-14"}},
                        "投稿日時": {"date": {"start": "2026-06-20T10:00:00.000Z"}},
                    },
                }],
                "has_more": True,
                "next_cursor": "cursor1",
            },
            {
                "results": [{
                    "id": "page2", "url": "https://notion.so/page2",
                    "properties": {
                        "名前": {"title": []},
                        "SNS種別": {"select": None},
                        "投稿文": {"rich_text": []},
                        "状態": {"select": None},
                        "作成日": {"date": None},
                        "投稿日時": {"date": None},
                    },
                }],
                "has_more": False,
            },
        ]
        posts = generator.fetch_all_posts(mock_notion, "db123")
        assert len(posts) == 2
        assert posts[0]["title"] == "投稿A"
        assert posts[0]["char_count"] == len("本文")
        assert posts[0]["scheduled"] == "2026-06-20 10:00"
        assert posts[1]["title"] == "(無題)"
        assert posts[1]["scheduled"] == ""
        assert mock_notion.databases.query.call_count == 2


class TestNotionUpdateHelpers:
    def test_update_status(self):
        mock_notion = MagicMock()
        generator.update_status(mock_notion, "page1", "承認済み")
        kwargs = mock_notion.pages.update.call_args.kwargs
        assert kwargs["page_id"] == "page1"
        assert kwargs["properties"]["状態"]["select"]["name"] == "承認済み"

    def test_update_schedule_sets_approved_and_datetime(self):
        mock_notion = MagicMock()
        generator.update_schedule(mock_notion, "page1", "2026-06-20T10:00:00")
        props = mock_notion.pages.update.call_args.kwargs["properties"]
        assert props["状態"]["select"]["name"] == "承認済み"
        assert props["投稿日時"]["date"]["start"] == "2026-06-20T10:00:00"

    def test_edit_post_updates_content_without_status(self):
        mock_notion = MagicMock()
        generator.edit_post(mock_notion, "page1", content="新しい本文")
        props = mock_notion.pages.update.call_args.kwargs["properties"]
        assert "状態" not in props
        assert props["投稿文"]["rich_text"][0]["text"]["content"] == "新しい本文"

    def test_cancel_schedule_resets_to_draft(self):
        mock_notion = MagicMock()
        generator.cancel_schedule(mock_notion, "page1")
        props = mock_notion.pages.update.call_args.kwargs["properties"]
        assert props["状態"]["select"]["name"] == "下書き"
        assert props["投稿日時"]["date"] is None

    def test_delete_post_archives(self):
        mock_notion = MagicMock()
        generator.delete_post(mock_notion, "page1")
        kwargs = mock_notion.pages.update.call_args.kwargs
        assert kwargs["page_id"] == "page1"
        assert kwargs["archived"] is True


# ── generator.SNS_HASHTAG_RULES / 生成プロンプト ──────────────────

class TestGenerateHashtagsParsing:
    def test_strips_code_fence(self):
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='```json\n{"hashtags": ["#a"], "strategy": "s"}\n```')]
        mock_client.messages.create.return_value = mock_message
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_hashtags("テーマ", "Instagram")
        assert result["hashtags"] == ["#a"]

    def test_sns_specific_rule_in_prompt(self):
        mock_client = MagicMock()
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text='{"hashtags": [], "strategy": "s"}')]
        mock_client.messages.create.return_value = mock_message
        with patch.object(generator, "_client", return_value=mock_client):
            generator.generate_hashtags("テーマ", "LINE")
        prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert generator.SNS_HASHTAG_RULES["LINE"]["note"] in prompt


# ── generator._create_json() リトライ ───────────────────────────
# 絵文字混じりの長文JSONでCladueがまれに構文エラーを返すケースの
# 自動リトライ・リトライ上限到達時の挙動を検証

class TestCreateJsonRetry:
    def _message(self, text):
        m = MagicMock()
        m.content = [MagicMock(text=text)]
        return m

    def test_retries_on_json_decode_error_then_succeeds(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            self._message('{"hashtags": ["#a"' ),  # 不正なJSON(途中で切れている)
            self._message('{"hashtags": ["#a"], "strategy": "s"}'),
        ]
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator._create_json("prompt", max_tokens=100)
        assert result == {"hashtags": ["#a"], "strategy": "s"}
        assert mock_client.messages.create.call_count == 2

    def test_raises_after_max_retries(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            self._message('{"hashtags": ["#a"'),
            self._message('{"hashtags": ["#a"'),
            self._message('{"hashtags": ["#a"'),
        ]
        with patch.object(generator, "_client", return_value=mock_client):
            with pytest.raises(ValueError):
                generator._create_json("prompt", max_tokens=100)
        assert mock_client.messages.create.call_count == 3
