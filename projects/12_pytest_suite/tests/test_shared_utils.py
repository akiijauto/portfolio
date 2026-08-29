"""shared/utils.py のテスト（extract_json / call_claude_json）。"""
import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import anthropic
import httpx
import pytest

ROOT = Path(__file__).parents[3]

import sys
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from shared import utils


def _message(text):
    m = MagicMock()
    m.content = [MagicMock(text=text)]
    return m


def _api_connection_error():
    return anthropic.APIConnectionError(request=httpx.Request("POST", "https://api.anthropic.com"))


# ── extract_json() ───────────────────────────────────────────────

class TestExtractJson:
    def test_plain_json_object(self):
        assert utils.extract_json('{"a": 1}') == {"a": 1}

    def test_plain_json_array(self):
        assert utils.extract_json('["a", "b"]') == ["a", "b"]

    def test_strips_code_fence_with_json_label(self):
        assert utils.extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_strips_code_fence_without_label(self):
        assert utils.extract_json('```\n{"a": 1}\n```') == {"a": 1}

    def test_raises_value_error_when_no_json(self):
        with pytest.raises(ValueError):
            utils.extract_json("no json here")

    def test_raises_value_error_on_malformed_json(self):
        with pytest.raises(ValueError):
            utils.extract_json('{"a": 1')


# ── call_claude_json() ───────────────────────────────────────────

class TestCallClaudeJsonRetry:
    def test_returns_parsed_json_on_first_success(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _message('{"ok": true}')
        result = utils.call_claude_json(mock_client, "claude-haiku-4-5-20251001", 100, "prompt")
        assert result == {"ok": True}
        assert mock_client.messages.create.call_count == 1

    def test_retries_on_json_decode_error_then_succeeds(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _message('{"ok": true'),  # 不正なJSON
            _message('{"ok": true}'),
        ]
        result = utils.call_claude_json(mock_client, "claude-haiku-4-5-20251001", 100, "prompt")
        assert result == {"ok": True}
        assert mock_client.messages.create.call_count == 2

    def test_raises_value_error_after_max_retries(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _message('{"ok": true'),
            _message('{"ok": true'),
            _message('{"ok": true'),
        ]
        with pytest.raises(ValueError):
            utils.call_claude_json(mock_client, "claude-haiku-4-5-20251001", 100, "prompt")
        assert mock_client.messages.create.call_count == 3

    def test_retries_on_transient_error_then_succeeds(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [_api_connection_error(), _message('{"ok": true}')]
        with patch.object(utils, "time") as mock_time:
            result = utils.call_claude_json(mock_client, "claude-haiku-4-5-20251001", 100, "prompt")
        assert result == {"ok": True}
        assert mock_client.messages.create.call_count == 2
        mock_time.sleep.assert_called_once()

    def test_raises_after_max_retries_on_transient_error(self):
        mock_client = MagicMock()
        mock_client.messages.create.side_effect = [
            _api_connection_error(), _api_connection_error(), _api_connection_error(),
        ]
        with patch.object(utils, "time"):
            with pytest.raises(anthropic.APIConnectionError):
                utils.call_claude_json(mock_client, "claude-haiku-4-5-20251001", 100, "prompt")
        assert mock_client.messages.create.call_count == 3

    def test_cache_prefix_sends_cached_content_blocks(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _message('{"ok": true}')
        result = utils.call_claude_json(
            mock_client, "claude-haiku-4-5-20251001", 100, "prompt",
            cache_prefix="fixed instructions",
        )
        assert result == {"ok": True}
        sent_content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert sent_content == [
            {"type": "text", "text": "fixed instructions", "cache_control": {"type": "ephemeral"}},
            {"type": "text", "text": "prompt"},
        ]

    def test_without_cache_prefix_sends_plain_string_content(self):
        mock_client = MagicMock()
        mock_client.messages.create.return_value = _message('{"ok": true}')
        utils.call_claude_json(mock_client, "claude-haiku-4-5-20251001", 100, "prompt")
        sent_content = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert sent_content == "prompt"


# ── is_credit_error() / handle_ai_error() ─────────────────────────

def _credit_balance_error():
    return anthropic.BadRequestError(
        message="Your credit balance is too low to access the Anthropic API",
        response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com")),
        body={"type": "error", "error": {"type": "invalid_request_error", "message": "Your credit balance is too low"}},
    )


class TestIsCreditError:
    def test_true_for_credit_balance_error(self):
        assert utils.is_credit_error(_credit_balance_error()) is True

    def test_false_for_other_bad_request_error(self):
        e = anthropic.BadRequestError(
            message="invalid request",
            response=httpx.Response(400, request=httpx.Request("POST", "https://api.anthropic.com")),
            body={"type": "error", "error": {"type": "invalid_request_error", "message": "invalid request"}},
        )
        assert utils.is_credit_error(e) is False

    def test_false_for_non_anthropic_error(self):
        assert utils.is_credit_error(ValueError("boom")) is False


class TestHandleAiError:
    def test_credit_error_returns_service_paused_and_notifies_admin(self):
        with patch("shared.notify.notify_admin") as mock_notify:
            from shared.errors import get as err
            result = utils.handle_ai_error(_credit_balance_error(), "test-project")
        assert result == err("service_paused")
        mock_notify.assert_called_once()
        assert "test-project" in mock_notify.call_args[0][0]

    def test_other_error_returns_ai_error_without_notifying(self):
        with patch("shared.notify.notify_admin") as mock_notify:
            from shared.errors import get as err
            result = utils.handle_ai_error(ValueError("boom"), "test-project")
        assert result == err("ai_error")
        mock_notify.assert_not_called()
