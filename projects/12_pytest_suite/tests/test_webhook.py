"""webhook.py のユニットテスト（11_webhook_relay）。"""
import hashlib
import hmac
import os
from unittest.mock import MagicMock, patch

import pytest

import webhook as wh


# ── 署名検証 ───────────────────────────────────────────────────

class TestVerifySignature:
    def test_no_secret_returns_false(self):
        """GITHUB_WEBHOOK_SECRET 未設定時は拒否する（5f84b68のセキュリティ修正後の挙動）。"""
        with patch.dict(os.environ, {}, clear=True):
            assert wh.verify_signature(b"payload", "sha256=anything") is False

    def test_valid_signature(self):
        secret = "mysecret"
        payload = b'{"ref":"refs/heads/main"}'
        sig = "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            assert wh.verify_signature(payload, sig) is True

    def test_invalid_signature_returns_false(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "mysecret"}):
            assert wh.verify_signature(b"payload", "sha256=badhash") is False

    def test_missing_sha256_prefix_returns_false(self):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "mysecret"}):
            assert wh.verify_signature(b"payload", "invalidsig") is False


# ── Embed生成 ──────────────────────────────────────────────────

class TestBuildEmbeds:
    def test_push_embed_has_title(self):
        payload = {
            "ref": "refs/heads/main",
            "commits": [{"message": "feat: add feature"}],
            "repository": {"full_name": "owner/repo"},
            "pusher": {"name": "touro"},
            "compare": "https://github.com/owner/repo/compare/abc...def",
        }
        embed = wh._build_push_embed(payload)
        assert "Push" in embed["title"]
        assert "owner/repo" in embed["title"]
        assert "feat: add feature" in embed["description"]
        assert embed["color"] == 0x3B82F6

    def test_push_embed_no_commits(self):
        payload = {
            "ref": "refs/heads/feat",
            "commits": [],
            "repository": {"full_name": "owner/repo"},
            "pusher": {"name": "touro"},
            "compare": "",
        }
        embed = wh._build_push_embed(payload)
        assert "0" in embed["description"]

    def test_pr_embed_opened(self):
        payload = {
            "action": "opened",
            "pull_request": {
                "number": 42,
                "title": "Add login feature",
                "html_url": "https://github.com/owner/repo/pull/42",
                "user": {"login": "touro"},
                "merged": False,
            },
            "repository": {"full_name": "owner/repo"},
        }
        embed = wh._build_pr_embed(payload)
        assert "#42" in embed["title"]
        assert "オープン" in embed["title"]
        assert embed["color"] == 0x22C55E

    def test_pr_embed_merged(self):
        payload = {
            "action": "closed",
            "pull_request": {
                "number": 10,
                "title": "Fix bug",
                "html_url": "",
                "user": {"login": "touro"},
                "merged": True,
            },
            "repository": {"full_name": "owner/repo"},
        }
        embed = wh._build_pr_embed(payload)
        assert "マージ" in embed["title"]
        assert embed["color"] == 0x8B5CF6

    def test_issue_embed_opened(self):
        payload = {
            "action": "opened",
            "issue": {
                "number": 7,
                "title": "Bug: login fails",
                "html_url": "https://github.com/owner/repo/issues/7",
                "user": {"login": "reporter"},
            },
            "repository": {"full_name": "owner/repo"},
        }
        embed = wh._build_issue_embed(payload)
        assert "#7" in embed["title"]
        assert "opened" in embed["title"]


# ── handle_event ──────────────────────────────────────────────

class TestHandleEvent:
    def test_ping_returns_200_pong(self):
        payload = {"zen": "Keep it simple."}
        status, msg = wh.handle_event("ping", payload)
        assert status == 200
        assert msg == "pong"

    def test_unknown_event_ignored(self):
        status, msg = wh.handle_event("star", {"action": "created"})
        assert status == 200
        assert msg == "ignored"

    def test_push_calls_discord(self):
        payload = {
            "ref": "refs/heads/main",
            "commits": [{"message": "test"}],
            "repository": {"full_name": "owner/repo"},
            "pusher": {"name": "touro"},
            "compare": "",
        }
        with patch.object(wh, "_send_discord_embed", return_value=True) as mock_send:
            status, msg = wh.handle_event("push", payload)
            assert status == 200
            assert msg == "ok"
            mock_send.assert_called_once()

    def test_discord_failure_still_returns_200(self):
        payload = {
            "ref": "refs/heads/main",
            "commits": [{"message": "test"}],
            "repository": {"full_name": "owner/repo"},
            "pusher": {"name": "touro"},
            "compare": "",
        }
        with patch.object(wh, "_send_discord_embed", return_value=False):
            status, msg = wh.handle_event("push", payload)
            assert status == 200


# ── ログ ────────────────────────────────────────────────────────

class TestLogs:
    def test_logs_are_thread_safe_list(self):
        before = len(wh.get_logs())
        wh._add_log("test", "ok", "unit test entry")
        after = len(wh.get_logs())
        assert after == before + 1

    def test_latest_log_first(self):
        wh._add_log("test", "ok", "first")
        wh._add_log("test", "ok", "second")
        logs = wh.get_logs()
        assert logs[0]["summary"] == "second"
