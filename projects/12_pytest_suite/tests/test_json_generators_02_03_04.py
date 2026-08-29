"""02/03/04: shared.call_claude_json への移行（コードフェンス除去・リトライ・max_tokens）を検証。"""
import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).parents[3]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _load(mod_name, project, filename):
    project_dir = ROOT / "projects" / project
    if str(project_dir) not in sys.path:
        sys.path.insert(0, str(project_dir))
    spec = importlib.util.spec_from_file_location(mod_name, project_dir / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


summarizer_02 = _load("summarizer_02", "02_web_article_summary", "summarizer.py")
summarizer_03 = _load("summarizer_03", "03_youtube_summary", "summarizer.py")
generator_04 = _load("generator_04", "04_mercari_listing", "generator.py")


def _message(text):
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    return m


class TestWebArticleSummary:
    def test_strips_code_fence_and_uses_correct_max_tokens(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _message(
            '```json\n{"title": "T", "summary_3": [], "summary_5": [], "sns": "S"}\n```'
        )
        with patch.object(summarizer_02, "client", mock_client):
            result = summarizer_02.summarize("https://example.com", "本文", "タイトル")
        assert result["title"] == "T"
        assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 3072

    def test_retries_on_malformed_json(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _message('{"title": "T"'),
            _message('{"title": "T", "summary_3": [], "summary_5": [], "sns": "S"}'),
        ]
        with patch.object(summarizer_02, "client", mock_client):
            result = summarizer_02.summarize("https://example.com", "本文", "タイトル")
        assert result["title"] == "T"
        assert mock_client.messages.create.call_count == 2


class TestYoutubeSummary:
    def test_strips_code_fence_and_uses_correct_max_tokens(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _message(
            '```json\n{"summary": "S", "points": [], "sns": "S", "category": "C"}\n```'
        )
        with patch.object(summarizer_03, "client", mock_client):
            result = summarizer_03.summarize("https://example.com", "タイトル", "字幕")
        assert result["summary"] == "S"
        assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 3072


class TestMercariListing:
    def test_strips_code_fence_and_uses_correct_max_tokens(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _message(
            '```json\n{"title": "T", "description": "D", "price_min": 100, '
            '"price_max": 200, "category": "C", "tips": []}\n```'
        )
        with patch.object(generator_04, "client", mock_client):
            result = generator_04.generate_listing("商品", "新品、未使用", "カテゴリ", "特徴")
        assert result["title"] == "T"
        assert mock_client.messages.create.call_args.kwargs["max_tokens"] == 3072
