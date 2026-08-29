import base64
import hashlib
import hmac
import json
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest

CHANNEL_SECRET = "test-channel-secret"


def _sign(body: str) -> str:
    digest = hmac.new(CHANNEL_SECRET.encode(), body.encode(), hashlib.sha256).digest()
    return base64.b64encode(digest).decode()


def _text_message_body(user_id: str, text: str, reply_token: str = "reply-token-1") -> str:
    return json.dumps({
        "destination": "dest",
        "events": [{
            "type": "message",
            "mode": "active",
            "timestamp": 1234567890,
            "source": {"type": "user", "userId": user_id},
            "replyToken": reply_token,
            "webhookEventId": "webhook-event-1",
            "deliveryContext": {"isRedelivery": False},
            "message": {"type": "text", "id": "msg1", "text": text, "quoteToken": "quote-token-1"},
        }],
    })


@pytest.fixture
def app(tmp_path, monkeypatch):
    monkeypatch.setenv("LINE_CHANNEL_SECRET", CHANNEL_SECRET)
    monkeypatch.setenv("LINE_CHANNEL_ACCESS_TOKEN", "dummy-token")

    import app as app_module
    monkeypatch.setattr(app_module, "BASE_DIR", tmp_path)
    app_module.handler = None
    flask_app = app_module.create_app(start_scheduler=False)
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    with app.test_client() as client:
        yield client


def test_webhook_rejects_invalid_signature(client):
    body = _text_message_body("user1", "テスト")
    res = client.post("/webhook", data=body, headers={"X-Line-Signature": "invalid"})
    assert res.status_code == 400


def test_webhook_registers_task_from_message(client, app):
    body = _text_message_body("user1", "明日までに資料を提出する")
    signature = _sign(body)

    fake_extraction = {"task_name": "資料の提出", "due_date": "2026-06-21", "category": "仕事"}
    fake_messaging_api = MagicMock()

    with patch("app._extract_task", return_value=fake_extraction), \
         patch("app._get_messaging_api", return_value=fake_messaging_api):
        res = client.post("/webhook", data=body, headers={"X-Line-Signature": signature})

    assert res.status_code == 200
    fake_messaging_api.reply_message.assert_called_once()

    with app.app_context():
        from models import Task
        tasks = Task.query.filter_by(line_user_id="user1").all()
        assert len(tasks) == 1
        assert tasks[0].task_name == "資料の提出"
        assert tasks[0].due_date == "2026-06-21"


def test_webhook_replies_task_list_for_ichiran(client, app):
    with app.app_context():
        from models import Task, db
        db.session.add(Task(line_user_id="user1", task_name="既存タスク", due_date="2026-06-25", category="仕事"))
        db.session.commit()

    body = _text_message_body("user1", "一覧")
    signature = _sign(body)
    fake_messaging_api = MagicMock()

    with patch("app._get_messaging_api", return_value=fake_messaging_api):
        res = client.post("/webhook", data=body, headers={"X-Line-Signature": signature})

    assert res.status_code == 200
    call_args = fake_messaging_api.reply_message.call_args[0][0]
    assert "既存タスク" in call_args.messages[0].text


def test_index_shows_tasks(client, app):
    with app.app_context():
        from models import Task, db
        db.session.add(Task(line_user_id="user1", task_name="表示確認タスク", category="その他"))
        db.session.commit()

    res = client.get("/")
    assert res.status_code == 200
    assert "表示確認タスク".encode() in res.data


def test_complete_task(client, app):
    with app.app_context():
        from models import Task, db
        task = Task(line_user_id="user1", task_name="完了予定タスク", category="その他")
        db.session.add(task)
        db.session.commit()
        task_id = task.id

    res = client.post(f"/tasks/{task_id}/complete", follow_redirects=True)
    assert res.status_code == 200

    with app.app_context():
        from models import Task, db
        assert db.session.get(Task, task_id).status == "完了"


def test_send_due_reminders_sends_push_for_due_tomorrow(app, monkeypatch):
    import app as app_module
    from datetime import datetime, timedelta

    tomorrow = (datetime.now(app_module.JST).date() + timedelta(days=1)).isoformat()

    with app.app_context():
        from models import Task, db
        db.session.add(Task(line_user_id="user1", task_name="締切タスク", due_date=tomorrow, category="仕事"))
        db.session.commit()

        fake_messaging_api = MagicMock()
        with patch("app._get_messaging_api", return_value=fake_messaging_api):
            sent = app_module.send_due_reminders()

        assert sent == 1
        fake_messaging_api.push_message.assert_called_once()


def test_extract_task_falls_back_on_ai_error():
    import app as app_module
    with patch("app.call_claude_json", side_effect=Exception("api error")):
        result = app_module._extract_task("買い物に行く")
    assert result["category"] == "その他"
