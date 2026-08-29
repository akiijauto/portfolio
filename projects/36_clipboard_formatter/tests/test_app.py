import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "history.db")
    app = app_module.create_app()
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_ok(client):
    res = client.get("/")
    assert res.status_code == 200


def test_api_format_requires_text(client):
    res = client.post("/api/format", json={"text": "", "mode": "proofread"})
    assert res.status_code == 400


def test_api_format_rejects_unknown_mode(client):
    res = client.post("/api/format", json={"text": "テスト", "mode": "unknown"})
    assert res.status_code == 400


def test_api_format_rejects_too_long_text(client):
    res = client.post("/api/format", json={"text": "あ" * 5001, "mode": "proofread"})
    assert res.status_code == 400


def test_api_format_returns_result_and_saves_history(client):
    with patch("app.call_claude_text", return_value="整形済みテキスト"):
        res = client.post("/api/format", json={"text": "元のてきすと", "mode": "proofread"})
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert data["result"] == "整形済みテキスト"

    history = app_module._load_history()
    assert len(history) == 1
    assert history[0]["mode"] == "proofread"


def test_api_format_handles_ai_error(client):
    with patch("app.call_claude_text", side_effect=Exception("api error")):
        res = client.post("/api/format", json={"text": "テスト", "mode": "summarize"})
    assert res.status_code == 502


def test_api_history_returns_json(client):
    with patch("app.call_claude_text", return_value="結果"):
        client.post("/api/format", json={"text": "テスト", "mode": "bullet"})

    res = client.get("/api/history")
    assert res.status_code == 200
    data = res.get_json()
    assert data["ok"] is True
    assert len(data["history"]) == 1


def test_cors_header_present_on_api_response(client):
    res = client.post(
        "/api/format",
        json={"text": "", "mode": "proofread"},
        headers={"Origin": "chrome-extension://abcdefghijklmnopabcdefghijklmnop"},
    )
    assert res.headers.get("Access-Control-Allow-Origin") == "chrome-extension://abcdefghijklmnopabcdefghijklmnop"
