"""02_web_article_summary のテスト（/search, /summarize エンドポイント + scraper.search_articles）。"""
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROJECT = ROOT / "projects" / "02_web_article_summary"
sys.path.insert(0, str(PROJECT))
for _mod in ("scraper", "summarizer", "app"):
    sys.modules.pop(_mod, None)

spec = importlib.util.spec_from_file_location("web_article_app", PROJECT / "app.py")
web_article_app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(web_article_app)

import scraper as web_article_scraper

flask_app = web_article_app.app
flask_app.root_path = str(PROJECT)
flask_app.template_folder = str(PROJECT / "templates")
flask_app.static_folder = str(PROJECT / "static")


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.test_client() as c:
        yield c


# ── /search ────────────────────────────────────────────────────────

class TestSearchEndpoint:
    def test_empty_keyword_returns_400(self, client):
        resp = client.post("/search", data={"keyword": ""})
        assert resp.status_code == 400

    def test_too_long_keyword_returns_400(self, client):
        resp = client.post("/search", data={"keyword": "a" * 201})
        assert resp.status_code == 400

    def test_api_key_unset_returns_503(self, client):
        with patch.object(web_article_app, "search_articles", side_effect=RuntimeError("TAVILY_API_KEY未設定")):
            resp = client.post("/search", data={"keyword": "テスト"})
        assert resp.status_code == 503

    def test_no_results_returns_404(self, client):
        with patch.object(web_article_app, "search_articles", return_value=[]):
            resp = client.post("/search", data={"keyword": "テスト"})
        assert resp.status_code == 404

    def test_success_returns_results(self, client):
        results = [{"title": "T1", "url": "https://example.com/1", "snippet": "S1"}]
        with patch.object(web_article_app, "search_articles", return_value=results):
            resp = client.post("/search", data={"keyword": "テスト"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["results"] == results

    def test_other_error_returns_500(self, client):
        with patch.object(web_article_app, "search_articles", side_effect=Exception("boom")):
            resp = client.post("/search", data={"keyword": "テスト"})
        assert resp.status_code == 500


# ── /summarize ────────────────────────────────────────────────────

class TestSummarizeEndpoint:
    def test_empty_url_returns_400(self, client):
        resp = client.post("/summarize", data={"url": ""})
        assert resp.status_code == 400

    def test_fetch_failure_returns_fetch_failed(self, client):
        with patch.object(web_article_app, "fetch_article", side_effect=Exception("network error")):
            resp = client.post("/summarize", data={"url": "https://example.com"})
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False

    def test_short_text_returns_js_site_error(self, client):
        with patch.object(web_article_app, "fetch_article", return_value=("短い", "タイトル")):
            resp = client.post("/summarize", data={"url": "https://example.com"})
        assert resp.status_code == 400

    def test_summarize_credit_error_returns_service_paused(self, client):
        import anthropic
        import httpx
        from shared.errors import get as err

        long_text = "本文" * 100
        credit_error = anthropic.BadRequestError(
            message="Your credit balance is too low to access the Anthropic API",
            response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com")),
            body={"type": "error", "error": {"type": "invalid_request_error", "message": "Your credit balance is too low"}},
        )
        with patch.object(web_article_app, "fetch_article", return_value=(long_text, "タイトル")), \
             patch.object(web_article_app, "summarize", side_effect=credit_error), \
             patch("shared.notify.notify_admin") as mock_notify:
            resp = client.post("/summarize", data={"url": "https://example.com"})
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["error"] == err("service_paused")
        mock_notify.assert_called_once()

    def test_success_returns_summary(self, client):
        long_text = "本文" * 100
        result = {"title": "T", "summary_3": ["a"], "summary_5": ["b"], "sns": "S"}
        with patch.object(web_article_app, "fetch_article", return_value=(long_text, "タイトル")), \
             patch.object(web_article_app, "summarize", return_value=result):
            resp = client.post("/summarize", data={"url": "https://example.com"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["data"]["title"] == "T"
        assert data["data"]["url"] == "https://example.com"


# ── scraper.search_articles() ───────────────────────────────────────

class TestSearchArticles:
    def test_raises_runtime_error_when_api_key_unset(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        with pytest.raises(RuntimeError):
            web_article_scraper.search_articles("テスト")

    def test_returns_parsed_results(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"results": [
            {"title": "T1", "url": "https://example.com/1", "content": "C1" * 200},
            {"title": "", "url": "https://example.com/2", "content": "C2"},
            {"title": "T3", "url": "", "content": "C3"},
        ]}
        with patch.object(web_article_scraper.requests, "post", return_value=mock_resp):
            results = web_article_scraper.search_articles("テスト", max_results=5)
        assert len(results) == 2
        assert results[0]["title"] == "T1"
        assert len(results[0]["snippet"]) == 200
        assert results[1]["title"] == "https://example.com/2"
