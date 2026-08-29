import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from app import create_app

VALID_FORM = {
    "name": "山田太郎",
    "email": "yamada@example.com",
    "subject": "料金について",
    "detail": "プランの料金体系について教えてください。",
}


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


def test_index_ok(client):
    res = client.get("/")
    assert res.status_code == 200


def test_submit_requires_name(client):
    data = dict(VALID_FORM)
    data["name"] = ""
    res = client.post("/submit", data=data, follow_redirects=True)
    assert res.status_code == 200
    assert "お名前を入力してください".encode() in res.data


def test_submit_rejects_invalid_email(client):
    data = dict(VALID_FORM)
    data["email"] = "not-an-email"
    res = client.post("/submit", data=data, follow_redirects=True)
    assert res.status_code == 200
    assert "メールアドレスの形式".encode() in res.data


def test_submit_saves_to_notion_and_sends_emails(client, monkeypatch):
    monkeypatch.setenv("NOTION_API_KEY", "dummy")
    monkeypatch.setenv("NOTION_DATABASE_ID", "dummy-db-id")
    monkeypatch.setenv("ADMIN_EMAIL", "admin@example.com")
    monkeypatch.setenv("SMTP_HOST", "smtp.example.com")

    fake_classification = {"category": "サポート依頼", "summary": "料金プランについての質問。"}
    fake_notion_client = MagicMock()
    fake_notion_client.pages.create.return_value = {"id": "page-123"}

    with patch("app._classify_inquiry", return_value=fake_classification), \
         patch("app._get_notion_client", return_value=fake_notion_client), \
         patch("app._send_email") as mock_send_email:
        res = client.post("/submit", data=VALID_FORM, follow_redirects=True)

    assert res.status_code == 200
    assert "受け付けました".encode() in res.data
    fake_notion_client.pages.create.assert_called_once()
    assert mock_send_email.call_count == 2


def test_submit_handles_notion_failure_gracefully(client, monkeypatch):
    monkeypatch.setenv("NOTION_API_KEY", "dummy")
    monkeypatch.setenv("NOTION_DATABASE_ID", "dummy-db-id")

    with patch("app._classify_inquiry", return_value={"category": "その他", "summary": "テスト"}), \
         patch("app._save_to_notion", side_effect=Exception("notion error")):
        res = client.post("/submit", data=VALID_FORM, follow_redirects=True)

    assert res.status_code == 200
    assert "送信に失敗しました".encode() in res.data


def test_classify_inquiry_falls_back_on_error():
    from app import _classify_inquiry

    with patch("app.call_claude_json", side_effect=Exception("api error")):
        result = _classify_inquiry("件名", "本文の詳細です。")

    assert result["category"] == "その他"
