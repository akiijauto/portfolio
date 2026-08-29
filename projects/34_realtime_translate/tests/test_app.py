import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DB_PATH", tmp_path / "test_history.db")
    app = app_module.create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


def _fake_stream(text, lang_label):
    yield "こん"
    yield "にちは"


def test_index_ok(client):
    res = client.get("/")
    assert res.status_code == 200


def test_translate_requires_text(client):
    res = client.post("/translate", json={"text": ""})
    assert res.status_code == 200
    assert "error".encode() in res.data


def test_translate_requires_gemini_key(client, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    res = client.post("/translate", json={"text": "hello"})
    assert res.status_code == 200
    assert "GEMINI_API_KEY".encode() in res.data


def test_translate_streams_all_languages(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    with patch("app._stream_translate", side_effect=_fake_stream):
        res = client.post("/translate", json={"text": "こんにちは"})
    body = res.data.decode()
    assert res.status_code == 200
    for code in ("ja", "en", "zh", "ko"):
        assert f'"lang": "{code}"' in body
    assert "event: complete" in body


def test_history_saved_after_translate(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    with patch("app._stream_translate", side_effect=_fake_stream):
        res = client.post("/translate", json={"text": "テスト"})
        res.get_data()  # ジェネレータをすべて消費し、履歴保存まで完了させる

    history = app_module._load_history()
    assert len(history) == 1
    assert history[0]["original_text"] == "テスト"
