"""14_seo_article_generator のテスト（app.py エンドポイント + generator.py ロジック）。"""
import json
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parents[3]
PROJECT = ROOT / "projects" / "14_seo_article_generator"

sys.path.insert(0, str(PROJECT))
for _mod in ("generator", "app"):
    sys.modules.pop(_mod, None)

spec = importlib.util.spec_from_file_location("seo_app", PROJECT / "app.py")
seo_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(seo_app_module)

flask_app = seo_app_module.app
generator = seo_app_module.generator
flask_app.root_path = str(PROJECT)
flask_app.template_folder = str(PROJECT / "templates")
flask_app.static_folder = str(PROJECT / "static")


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    with flask_app.test_client() as c:
        yield c


SAMPLE_OUTLINE = {
    "title": "サンプルタイトル",
    "meta_desc": "メタ説明",
    "intro_hook": "フック文",
    "sections": [{"h2": "見出し1", "purpose": "目的1", "h3s": ["小見出しA"]}],
    "conclusion_point": "まとめの要点",
    "faq": ["質問1", "質問2", "質問3"],
}


# ── / ────────────────────────────────────────────────────────────

class TestIndex:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# ── /outline ─────────────────────────────────────────────────────

class TestOutlineEndpoint:
    def test_empty_keyword_returns_400(self, client):
        resp = client.post("/outline", data={"keyword": ""})
        assert resp.status_code == 400

    def test_too_long_keyword_returns_400(self, client):
        resp = client.post("/outline", data={"keyword": "a" * 201})
        assert resp.status_code == 400

    def test_invalid_article_type_falls_back_to_default(self, client):
        with patch.object(generator, "generate_outline", return_value=SAMPLE_OUTLINE) as mock_gen:
            resp = client.post("/outline", data={
                "keyword": "テスト", "article_type": "存在しないタイプ",
            })
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[1] == "解説記事"

    def test_invalid_tone_falls_back_to_default(self, client):
        with patch.object(generator, "generate_outline", return_value=SAMPLE_OUTLINE) as mock_gen:
            resp = client.post("/outline", data={
                "keyword": "テスト", "tone": "存在しない文体",
            })
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[2] == "丁寧（です/ます体）"

    def test_target_chars_clamped_to_minimum(self, client):
        with patch.object(generator, "generate_outline", return_value=SAMPLE_OUTLINE) as mock_gen:
            resp = client.post("/outline", data={"keyword": "テスト", "target_chars": "10"})
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[3] == 500

    def test_target_chars_clamped_to_maximum(self, client):
        with patch.object(generator, "generate_outline", return_value=SAMPLE_OUTLINE) as mock_gen:
            resp = client.post("/outline", data={"keyword": "テスト", "target_chars": "100000"})
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[3] == 5000

    def test_invalid_target_chars_defaults_to_2000(self, client):
        with patch.object(generator, "generate_outline", return_value=SAMPLE_OUTLINE) as mock_gen:
            resp = client.post("/outline", data={"keyword": "テスト", "target_chars": "abc"})
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[3] == 2000

    def test_success_returns_outline(self, client):
        with patch.object(generator, "generate_outline", return_value=SAMPLE_OUTLINE):
            resp = client.post("/outline", data={"keyword": "テスト"})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["outline"]["title"] == "サンプルタイトル"

    def test_generation_error_returns_500(self, client):
        with patch.object(generator, "generate_outline", side_effect=Exception("boom")):
            resp = client.post("/outline", data={"keyword": "テスト"})
        assert resp.status_code == 500


# ── /generate ────────────────────────────────────────────────────

class TestGenerateEndpoint:
    def test_no_keyword_returns_400(self, client):
        resp = client.post("/generate", data={
            "keyword": "", "outline": json.dumps(SAMPLE_OUTLINE),
        })
        assert resp.status_code == 400

    def test_invalid_outline_json_returns_400(self, client):
        resp = client.post("/generate", data={"keyword": "テスト", "outline": "not-json"})
        assert resp.status_code == 400

    def test_success_returns_article_with_char_count(self, client):
        article_text = "# サンプルタイトル\n\n本文です。"
        with patch.object(generator, "generate_article", return_value=article_text):
            resp = client.post("/generate", data={
                "keyword": "テスト", "outline": json.dumps(SAMPLE_OUTLINE),
            })
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["article"] == article_text
        assert data["char_count"] == len(article_text)

    def test_generation_error_returns_500(self, client):
        with patch.object(generator, "generate_article", side_effect=Exception("boom")):
            resp = client.post("/generate", data={
                "keyword": "テスト", "outline": json.dumps(SAMPLE_OUTLINE),
            })
        assert resp.status_code == 500


# ── generator.generate_outline() ────────────────────────────────
# 振り返り.md記載の「コードフェンス除去」「競合分析結果の1200文字切り詰め」を検証

def _mock_client_with_text(text):
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=text)]
    mock_client.messages.create.return_value = mock_message
    return mock_client


class TestGenerateOutlineParsing:
    def test_strips_code_fence_with_json_label(self):
        mock_client = _mock_client_with_text('```json\n{"title": "T1", "sections": []}\n```')
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_outline("kw", "解説記事", "丁寧（です/ます体）", 1000)
        assert result["title"] == "T1"

    def test_strips_code_fence_without_json_label(self):
        mock_client = _mock_client_with_text('```\n{"title": "T2", "sections": []}\n```')
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_outline("kw", "解説記事", "丁寧（です/ます体）", 1000)
        assert result["title"] == "T2"

    def test_plain_json_without_fence(self):
        mock_client = _mock_client_with_text('{"title": "T3", "sections": []}')
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_outline("kw", "解説記事", "丁寧（です/ます体）", 1000)
        assert result["title"] == "T3"

    def test_competitor_context_truncated_to_1200_chars(self):
        mock_client = _mock_client_with_text('{"title": "T", "sections": []}')
        long_context = "あ" * 2000
        with patch.object(generator, "_client", return_value=mock_client):
            generator.generate_outline("kw", "解説記事", "丁寧（です/ます体）", 1000, long_context)
        prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "あ" * 1200 in prompt
        assert "あ" * 1201 not in prompt


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
            self._message('{"title": "T"'),  # 不正なJSON
            self._message('{"title": "T", "sections": []}'),
        ]
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator._create_json("prompt", max_tokens=100)
        assert result == {"title": "T", "sections": []}
        assert mock_client.messages.create.call_count == 2

    def test_raises_after_max_retries(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            self._message('{"title": "T"'),
            self._message('{"title": "T"'),
            self._message('{"title": "T"'),
        ]
        with patch.object(generator, "_client", return_value=mock_client):
            with pytest.raises(ValueError):
                generator._create_json("prompt", max_tokens=100)
        assert mock_client.messages.create.call_count == 3
