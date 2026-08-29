"""16_ad_copy_generator のテスト（app.py エンドポイント + generator.py ロジック）。"""
import json
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parents[3]
PROJECT = ROOT / "projects" / "16_ad_copy_generator"

sys.path.insert(0, str(PROJECT))
for _mod in ("generator", "app"):
    sys.modules.pop(_mod, None)

spec = importlib.util.spec_from_file_location("ad_app", PROJECT / "app.py")
ad_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ad_app_module)

flask_app = ad_app_module.app
generator = ad_app_module.generator
flask_app.root_path = str(PROJECT)
flask_app.template_folder = str(PROJECT / "templates")
flask_app.static_folder = str(PROJECT / "static")


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.test_client() as c:
        yield c


SAMPLE_DATA = {
    "google": {
        "headlines": ["見出し1", "見出し2"],
        "descriptions": ["説明1", "説明2", "説明3", "説明4"],
    },
    "meta": {
        "primary_text": "プライマリテキスト",
        "headline": "見出し",
        "description": "説明文",
        "cta_options": ["詳しくはこちら", "今すぐ申し込む", "資料請求"],
    },
    "line": {"title": "タイトル", "text": "広告テキスト"},
    "ab_variants": {
        "google_alt_headline": "別バリエーション見出し",
        "meta_alt_primary": "別バリエーション本文",
    },
    "copy_points": "効果的な理由の解説",
}


# ── / ────────────────────────────────────────────────────────────

class TestIndex:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# ── /generate ────────────────────────────────────────────────────

class TestGenerateEndpoint:
    def _form(self, **overrides):
        data = {"product": "商品A", "target": "20代女性", "usp": "高品質で低価格"}
        data.update(overrides)
        return data

    def test_missing_product_returns_400(self, client):
        resp = client.post("/generate", data=self._form(product=""))
        assert resp.status_code == 400

    def test_missing_target_returns_400(self, client):
        resp = client.post("/generate", data=self._form(target=""))
        assert resp.status_code == 400

    def test_missing_usp_returns_400(self, client):
        resp = client.post("/generate", data=self._form(usp=""))
        assert resp.status_code == 400

    def test_too_long_product_returns_400(self, client):
        resp = client.post("/generate", data=self._form(product="a" * 101))
        assert resp.status_code == 400

    def test_too_long_target_returns_400(self, client):
        resp = client.post("/generate", data=self._form(target="a" * 101))
        assert resp.status_code == 400

    def test_too_long_usp_returns_400(self, client):
        resp = client.post("/generate", data=self._form(usp="a" * 301))
        assert resp.status_code == 400

    def test_invalid_goal_falls_back_to_default(self, client):
        with patch.object(generator, "generate_all", return_value=SAMPLE_DATA) as mock_gen:
            resp = client.post("/generate", data=self._form(goal="存在しない目的"))
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[4] == "リード獲得"

    def test_success_returns_data(self, client):
        with patch.object(generator, "generate_all", return_value=SAMPLE_DATA):
            resp = client.post("/generate", data=self._form())
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["google"] == SAMPLE_DATA["google"]
        assert data["copy_points"] == SAMPLE_DATA["copy_points"]

    def test_generation_error_returns_500(self, client):
        with patch.object(generator, "generate_all", side_effect=Exception("boom")):
            resp = client.post("/generate", data=self._form())
        assert resp.status_code == 500


# ── generator.generate_all() ─────────────────────────────────────
# コードフェンス除去とプロンプト内容を検証

def _mock_client_with_text(text):
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=text)]
    mock_client.messages.create.return_value = mock_message
    return mock_client


class TestGenerateAllParsing:
    def test_strips_code_fence_with_json_label(self):
        mock_client = _mock_client_with_text('```json\n{"copy_points": "OK"}\n```')
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_all("商品A", "20代女性", "高品質", "", "リード獲得")
        assert result["copy_points"] == "OK"

    def test_strips_code_fence_without_json_label(self):
        mock_client = _mock_client_with_text('```\n{"copy_points": "OK2"}\n```')
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_all("商品A", "20代女性", "高品質", "", "リード獲得")
        assert result["copy_points"] == "OK2"

    def test_plain_json_without_fence(self):
        mock_client = _mock_client_with_text('{"copy_points": "OK3"}')
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_all("商品A", "20代女性", "高品質", "", "リード獲得")
        assert result["copy_points"] == "OK3"

    def test_prompt_includes_goal_description(self):
        mock_client = _mock_client_with_text('{"copy_points": "OK"}')
        with patch.object(generator, "_client", return_value=mock_client):
            generator.generate_all("商品A", "20代女性", "高品質", "", "認知拡大")
        prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert generator.GOALS["認知拡大"] in prompt

    def test_prompt_uses_default_when_industry_empty(self):
        mock_client = _mock_client_with_text('{"copy_points": "OK"}')
        with patch.object(generator, "_client", return_value=mock_client):
            generator.generate_all("商品A", "20代女性", "高品質", "", "リード獲得")
        prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "【業界】指定なし" in prompt


# ── generator._create_json() リトライ ───────────────────────────
# Claudeがまれに返す構文エラーJSONの自動リトライを検証

class TestCreateJsonRetry:
    def _message(self, text):
        m = MagicMock()
        m.content = [MagicMock(text=text)]
        return m

    def test_retries_on_json_decode_error_then_succeeds(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            self._message('{"copy_points": "OK"'),  # 不正なJSON
            self._message('{"copy_points": "OK"}'),
        ]
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator._create_json("prompt", max_tokens=100)
        assert result == {"copy_points": "OK"}
        assert mock_client.messages.create.call_count == 2

    def test_raises_after_max_retries(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            self._message('{"copy_points": "OK"'),
            self._message('{"copy_points": "OK"'),
            self._message('{"copy_points": "OK"'),
        ]
        with patch.object(generator, "_client", return_value=mock_client):
            with pytest.raises(ValueError):
                generator._create_json("prompt", max_tokens=100)
        assert mock_client.messages.create.call_count == 3
