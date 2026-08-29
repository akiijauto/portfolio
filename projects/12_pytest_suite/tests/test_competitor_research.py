"""13_competitor_research のテスト（app.py エンドポイント + analyzer.py ロジック）。"""
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest
from shared import utils as shared_utils

ROOT = Path(__file__).parents[3]
PROJECT = ROOT / "projects" / "13_competitor_research"

sys.path.insert(0, str(PROJECT))
for _mod in ("analyzer", "app"):
    sys.modules.pop(_mod, None)

spec = importlib.util.spec_from_file_location("competitor_app", PROJECT / "app.py")
competitor_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(competitor_app_module)

flask_app = competitor_app_module.app
analyzer = competitor_app_module.analyzer
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


# ── /search ──────────────────────────────────────────────────────

class TestSearchEndpoint:
    def test_empty_keyword_returns_400(self, client):
        resp = client.post("/search", data={"keyword": ""})
        assert resp.status_code == 400

    def test_too_long_keyword_returns_400(self, client):
        resp = client.post("/search", data={"keyword": "a" * 201})
        assert resp.status_code == 400

    def test_no_results_returns_404(self, client):
        with patch.object(analyzer, "search_competitors", return_value=[]):
            resp = client.post("/search", data={"keyword": "テスト"})
        assert resp.status_code == 404

    def test_success_returns_urls(self, client):
        urls = ["https://example.com/a", "https://example.com/b"]
        with patch.object(analyzer, "search_competitors", return_value=urls):
            resp = client.post("/search", data={"keyword": "テスト"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["urls"] == urls

    def test_search_error_returns_500(self, client):
        with patch.object(analyzer, "search_competitors", side_effect=Exception("boom")):
            resp = client.post("/search", data={"keyword": "テスト"})
        assert resp.status_code == 500


# ── /analyze ─────────────────────────────────────────────────────

SAMPLE_PAGE = {
    "url": "https://example.com", "domain": "example.com", "title": "サンプルページ",
    "meta_desc": "説明", "h1": ["見出し"], "h2": [], "h3": [], "char_count": 1000, "ok": True,
}


class TestAnalyzeEndpoint:
    def test_empty_keyword_returns_400(self, client):
        resp = client.post("/analyze", data={"keyword": "", "urls": "https://example.com"})
        assert resp.status_code == 400

    def test_no_valid_urls_returns_400(self, client):
        resp = client.post("/analyze", data={"keyword": "テスト", "urls": "not-a-url"})
        assert resp.status_code == 400

    def test_success_returns_pages_and_analysis(self, client):
        with patch.object(analyzer, "scrape_page", return_value=SAMPLE_PAGE), \
             patch.object(analyzer, "analyze_with_claude", return_value="# レポート"):
            resp = client.post("/analyze", data={
                "keyword": "テスト", "urls": "https://example.com",
            })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["pages"] == [SAMPLE_PAGE]
        assert data["analysis"] == "# レポート"

    def test_urls_limited_to_5(self, client):
        urls = "\n".join(f"https://example.com/{i}" for i in range(10))
        with patch.object(analyzer, "scrape_page", return_value=SAMPLE_PAGE) as mock_scrape, \
             patch.object(analyzer, "analyze_with_claude", return_value="ok"):
            resp = client.post("/analyze", data={"keyword": "テスト", "urls": urls})
        assert resp.status_code == 200
        assert mock_scrape.call_count == 5

    def test_analyze_error_returns_500(self, client):
        with patch.object(analyzer, "scrape_page", side_effect=Exception("boom")):
            resp = client.post("/analyze", data={
                "keyword": "テスト", "urls": "https://example.com",
            })
        assert resp.status_code == 500


# ── analyzer.search_competitors() ───────────────────────────────
# TAVILY_API_KEYの有無によるTavily/DuckDuckGoの振り分けを検証

class TestSearchCompetitorsDispatch:
    def test_uses_tavily_when_api_key_set(self, monkeypatch):
        monkeypatch.setenv("TAVILY_API_KEY", "tvly-test")
        with patch.object(analyzer, "_search_tavily", return_value=["https://example.com"]) as mock_tavily, \
             patch.object(analyzer, "_search_duckduckgo") as mock_ddg:
            urls = analyzer.search_competitors("テスト")
        assert urls == ["https://example.com"]
        mock_tavily.assert_called_once_with("テスト", "tvly-test", 5)
        mock_ddg.assert_not_called()

    def test_falls_back_to_duckduckgo_when_no_api_key(self, monkeypatch):
        monkeypatch.delenv("TAVILY_API_KEY", raising=False)
        with patch.object(analyzer, "_search_tavily") as mock_tavily, \
             patch.object(analyzer, "_search_duckduckgo", return_value=["https://example.com"]) as mock_ddg:
            urls = analyzer.search_competitors("テスト")
        assert urls == ["https://example.com"]
        mock_ddg.assert_called_once_with("テスト", 5)
        mock_tavily.assert_not_called()


# ── analyzer._search_tavily() ────────────────────────────────────
# Tavily Search APIのレスポンス解析を検証

class TestSearchTavily:
    def test_extracts_urls_from_results(self):
        resp = MagicMock()
        resp.json.return_value = {"results": [
            {"title": "A", "url": "https://example.com/a"},
            {"title": "B", "url": "https://example.com/b"},
        ]}
        with patch.object(analyzer.requests, "post", return_value=resp) as mock_post:
            urls = analyzer._search_tavily("テスト", "tvly-test", 5)
        assert urls == ["https://example.com/a", "https://example.com/b"]
        called_headers = mock_post.call_args.kwargs["headers"]
        assert called_headers["Authorization"] == "Bearer tvly-test"

    def test_max_results_limit(self):
        resp = MagicMock()
        resp.json.return_value = {"results": [
            {"title": f"P{i}", "url": f"https://example.com/{i}"} for i in range(10)
        ]}
        with patch.object(analyzer.requests, "post", return_value=resp):
            urls = analyzer._search_tavily("テスト", "tvly-test", 3)
        assert len(urls) == 3


# ── analyzer._search_duckduckgo() ────────────────────────────────
# 振り返り.md記載の「DDGリダイレクトURL抽出」「広告URL除外」のロジックを検証

class TestSearchDuckDuckGo:
    def _mock_response(self, html):
        resp = MagicMock()
        resp.text = html
        return resp

    def test_extracts_real_url_from_uddg_redirect(self):
        html = (
            '<a class="result__a" '
            'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Farticle&rut=abc">Example</a>'
        )
        with patch.object(analyzer.requests, "get", return_value=self._mock_response(html)):
            urls = analyzer._search_duckduckgo("テスト")
        assert urls == ["https://example.com/article"]

    def test_excludes_ad_urls_from_uddg(self):
        html = (
            '<a class="result__a" '
            'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fduckduckgo.com%2Fy.js%3Fad_domain%3Dexample.com">Ad</a>'
            '<a class="result__a" '
            'href="//duckduckgo.com/l/?uddg=https%3A%2F%2Fexample.com%2Freal">Real</a>'
        )
        with patch.object(analyzer.requests, "get", return_value=self._mock_response(html)):
            urls = analyzer._search_duckduckgo("テスト")
        assert urls == ["https://example.com/real"]

    def test_direct_http_links_included(self):
        html = '<a class="result__a" href="https://example.com/direct">Direct</a>'
        with patch.object(analyzer.requests, "get", return_value=self._mock_response(html)):
            urls = analyzer._search_duckduckgo("テスト")
        assert urls == ["https://example.com/direct"]

    def test_max_results_limit(self):
        html = "".join(
            f'<a class="result__a" href="https://example.com/{i}">Page{i}</a>'
            for i in range(10)
        )
        with patch.object(analyzer.requests, "get", return_value=self._mock_response(html)):
            urls = analyzer._search_duckduckgo("テスト", max_results=3)
        assert len(urls) == 3


# ── analyzer.scrape_page() ───────────────────────────────────────
# 振り返り.md記載の「エンコーディング誤検出のフォールバック」を検証

class TestScrapePage:
    def test_iso8859_encoding_falls_back_to_apparent(self):
        resp = MagicMock()
        resp.encoding = "ISO-8859-1"
        resp.apparent_encoding = "utf-8"
        resp.text = "<html><head><title>テスト</title></head><body><h1>見出し</h1></body></html>"
        resp.url = "https://example.com/page"
        with patch.object(analyzer.requests, "get", return_value=resp):
            page = analyzer.scrape_page("https://example.com/page")
        assert page["ok"] is True
        assert page["title"] == "テスト"
        assert page["h1"] == ["見出し"]

    def test_scrape_failure_returns_error_dict(self):
        with patch.object(analyzer.requests, "get", side_effect=Exception("connection error")):
            page = analyzer.scrape_page("https://example.com")
        assert page["ok"] is False
        assert "error" in page


# ── analyzer.analyze_with_claude() リトライ ─────────────────────
# Claude API一時エラー（429/5xx/接続エラー）時の自動リトライと、
# リトライ上限到達時の挙動を検証

def _api_connection_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))


class TestAnalyzeWithClaudeRetry:
    def test_retries_on_transient_error_then_succeeds(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        success_resp = MagicMock()
        success_resp.content = [MagicMock(text="# レポート")]
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [_api_connection_error(), success_resp]

        with patch.object(analyzer.anthropic, "Anthropic", return_value=mock_client), \
             patch.object(shared_utils.time, "sleep") as mock_sleep:
            result = analyzer.analyze_with_claude("テスト", [SAMPLE_PAGE])

        assert result == "# レポート"
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    def test_raises_after_max_retries(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "test-key")
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _api_connection_error(), _api_connection_error(), _api_connection_error(),
        ]

        with patch.object(analyzer.anthropic, "Anthropic", return_value=mock_client), \
             patch.object(shared_utils.time, "sleep"):
            with pytest.raises(anthropic.APIConnectionError):
                analyzer.analyze_with_claude("テスト", [SAMPLE_PAGE])

        assert mock_client.messages.create.call_count == 3


# ── /analyze のAIエラー分類 ──────────────────────────────────────
# Claude APIのエラー種別に応じて、ユーザー向けメッセージとステータスを分ける

class TestAnalyzeEndpointAIErrors:
    def _response(self, status_code):
        resp = MagicMock(spec=httpx.Response)
        resp.status_code = status_code
        resp.headers = {}
        resp.request = httpx.Request("POST", "https://api.anthropic.com")
        return resp

    def test_rate_limit_returns_503_with_busy_message(self, client):
        err = anthropic.RateLimitError("rate limited", response=self._response(429), body=None)
        with patch.object(analyzer, "scrape_page", return_value=SAMPLE_PAGE), \
             patch.object(analyzer, "analyze_with_claude", side_effect=err):
            resp = client.post("/analyze", data={"keyword": "テスト", "urls": "https://example.com"})
        assert resp.status_code == 503
        data = resp.get_json()
        assert data["ok"] is False
        assert "混み合" in data["error"]

    def test_auth_error_returns_500_with_missing_key_message(self, client):
        err = anthropic.AuthenticationError("invalid key", response=self._response(401), body=None)
        with patch.object(analyzer, "scrape_page", return_value=SAMPLE_PAGE), \
             patch.object(analyzer, "analyze_with_claude", side_effect=err):
            resp = client.post("/analyze", data={"keyword": "テスト", "urls": "https://example.com"})
        assert resp.status_code == 500
        data = resp.get_json()
        assert data["ok"] is False
        assert "ANTHROPIC_API_KEY" in data["error"]
