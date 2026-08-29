"""09_daily_bot scheduler.py のユニットテスト。"""
import os
from unittest.mock import MagicMock, patch

import pytest

import scheduler as sched


class TestRunDigest:
    def test_no_webhook_url_returns_error(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DISCORD_WEBHOOK_URL", None)
            result = sched.run_digest()
        assert result["ok"] is False
        assert "DISCORD_WEBHOOK_URL" in result["error"]

    def test_discord_post_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None

        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test/webhook"}):
            with patch("scheduler.requests.post", return_value=mock_resp) as mock_post:
                with patch("scheduler._build_message", return_value="テストメッセージ"):
                    result = sched.run_digest()

        assert result["ok"] is True
        assert result["message"] == "テストメッセージ"
        mock_post.assert_called_once()
        call_kwargs = mock_post.call_args
        assert call_kwargs[1]["json"]["content"] == "テストメッセージ"

    def test_discord_post_failure_returns_error(self):
        import requests as req
        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test/webhook"}):
            with patch("scheduler.requests.post", side_effect=req.RequestException("timeout")):
                with patch("scheduler._build_message", return_value="msg"):
                    result = sched.run_digest()

        assert result["ok"] is False
        assert "timeout" in result["error"]

    def test_log_added_on_success(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.return_value = None
        before = len(sched.get_logs())

        with patch.dict(os.environ, {"DISCORD_WEBHOOK_URL": "https://discord.test/webhook"}):
            with patch("scheduler.requests.post", return_value=mock_resp):
                with patch("scheduler._build_message", return_value="msg"):
                    sched.run_digest()

        logs = sched.get_logs()
        assert len(logs) > before
        assert logs[0]["status"] == "success"

    def test_log_added_on_error(self):
        with patch.dict(os.environ, {}, clear=True):
            os.environ.pop("DISCORD_WEBHOOK_URL", None)
            before = len(sched.get_logs())
            sched.run_digest()

        logs = sched.get_logs()
        assert len(logs) > before
        assert logs[0]["status"] == "error"


class TestSchedulerSingleton:
    def test_get_scheduler_returns_same_instance(self):
        s1 = sched.get_scheduler()
        s2 = sched.get_scheduler()
        assert s1 is s2

    def test_set_schedule_updates_state(self):
        sched.set_schedule(9, 30)
        info = sched.get_job_info()
        assert info["hour"] == 9
        assert info["minute"] == 30
        assert info["scheduled"] is True
