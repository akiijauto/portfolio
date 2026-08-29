import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "TOKEN_PATH", tmp_path / "google_token.json")
    # start_scheduler=Falseでテスト中にAPSchedulerのジョブを起動しない
    app = app_module.create_app(start_scheduler=False)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


def test_index_without_auth_shows_login_link(client):
    res = client.get("/")
    assert res.status_code == 200
    assert "Googleでログイン".encode() in res.data


def test_index_with_auth_shows_summary(client, monkeypatch):
    fake_creds = MagicMock()
    monkeypatch.setattr(app_module, "_load_credentials", lambda: fake_creds)
    monkeypatch.setattr(app_module, "_fetch_week_events", lambda creds: [
        {"summary": "会議A", "start": "2026-06-22T10:00:00+09:00"},
    ])
    monkeypatch.setattr(app_module, "_summarize_events", lambda events: "会議Aが最重要です。")

    res = client.get("/")
    assert res.status_code == 200
    assert "会議Aが最重要です".encode() in res.data
    assert "会議A".encode() in res.data


def test_run_now_without_auth(client, monkeypatch):
    monkeypatch.setattr(app_module, "_load_credentials", lambda: None)
    res = client.post("/run-now", follow_redirects=True)
    assert res.status_code == 200
    assert "未連携".encode() in res.data


def test_run_now_sends_summary(client, monkeypatch):
    fake_creds = MagicMock()
    monkeypatch.setattr(app_module, "_load_credentials", lambda: fake_creds)
    monkeypatch.setattr(app_module, "_fetch_week_events", lambda creds: [
        {"summary": "会議A", "start": "2026-06-22T10:00:00+09:00"},
    ])
    monkeypatch.setattr(app_module, "_summarize_events", lambda events: "会議Aが最重要です。")

    with patch("app._send_discord") as mock_discord, patch("app._send_email") as mock_email:
        res = client.post("/run-now", follow_redirects=True)

    assert res.status_code == 200
    assert "送信しました".encode() in res.data
    mock_discord.assert_called_once()
    mock_email.assert_called_once()


def test_summarize_events_handles_empty_list():
    result = app_module._summarize_events([])
    assert "予定がありません" in result


def test_summarize_events_falls_back_on_ai_error():
    events = [{"summary": "会議A", "start": "2026-06-22T10:00:00+09:00"}]
    with patch("app.call_claude_text", side_effect=Exception("api error")):
        result = app_module._summarize_events(events)
    assert "会議A" in result


def test_send_daily_summary_returns_empty_without_auth(monkeypatch):
    monkeypatch.setattr(app_module, "_load_credentials", lambda: None)
    result = app_module.send_daily_summary()
    assert result == ""
