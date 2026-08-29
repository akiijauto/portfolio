import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
import app as app_module


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(app_module, "DAILY_COMMENT_PATH", tmp_path / "daily_comment.json")
    app_module.alert_state["usdjpy_threshold"] = None
    # start_background=Falseでyfinanceへの実通信を伴う無限ループを起動しない
    app = app_module.create_app(start_background=False)
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


def test_index_ok(client):
    res = client.get("/")
    assert res.status_code == 200


def test_set_alert_threshold(client):
    res = client.post("/alert", data={"usdjpy_threshold": "155.5"}, follow_redirects=True)
    assert res.status_code == 200
    assert app_module.alert_state["usdjpy_threshold"] == 155.5


def test_clear_alert_threshold(client):
    app_module.alert_state["usdjpy_threshold"] = 150.0
    res = client.post("/alert", data={"usdjpy_threshold": ""}, follow_redirects=True)
    assert res.status_code == 200
    assert app_module.alert_state["usdjpy_threshold"] is None


def test_set_alert_rejects_non_numeric(client):
    res = client.post("/alert", data={"usdjpy_threshold": "abc"}, follow_redirects=True)
    assert res.status_code == 200
    assert "数値を入力してください".encode() in res.data


def test_check_alert_triggers_when_above_threshold():
    app_module.alert_state["usdjpy_threshold"] = 150.0
    alert = app_module._check_alert({"usdjpy": 151.0})
    assert alert == {"pair": "USD/JPY", "rate": 151.0, "threshold": 150.0}


def test_check_alert_none_when_below_threshold():
    app_module.alert_state["usdjpy_threshold"] = 150.0
    alert = app_module._check_alert({"usdjpy": 149.0})
    assert alert is None


def test_fetch_market_data_handles_errors():
    with patch("app.yf.Ticker", side_effect=Exception("network error")):
        data = app_module._fetch_market_data()
    assert all(value is None for value in data.values())


def test_daily_comment_cached_per_day(client, monkeypatch):
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    with patch("app.call_claude_text", return_value="市場は落ち着いています。") as mock_call:
        first = app_module._get_daily_comment()
        second = app_module._get_daily_comment()
    assert first == "市場は落ち着いています。"
    assert second == first
    mock_call.assert_called_once()
