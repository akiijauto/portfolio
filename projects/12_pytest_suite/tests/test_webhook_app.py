"""11_webhook_relay app.py の Flaskエンドポイントテスト。"""
import hashlib
import hmac
import importlib.util
import json
import os
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).parents[3]
PROJECT = ROOT / "projects" / "11_webhook_relay"

spec = importlib.util.spec_from_file_location("relay_app", PROJECT / "app.py")
relay_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(relay_module)

relay_app = relay_module.app
relay_app.root_path = str(PROJECT)
relay_app.template_folder = str(PROJECT / "templates")
relay_app.static_folder = str(PROJECT / "static")


@pytest.fixture
def client():
    relay_app.config["TESTING"] = True
    with relay_app.test_client() as c:
        yield c


PUSH_PAYLOAD = json.dumps({
    "ref": "refs/heads/main",
    "commits": [{"message": "feat: new feature"}],
    "repository": {"full_name": "owner/repo"},
    "pusher": {"name": "touro"},
    "compare": "https://github.com",
}).encode()


def _make_sig(payload: bytes, secret: str) -> str:
    return "sha256=" + hmac.new(secret.encode(), payload, hashlib.sha256).hexdigest()


class TestGithubWebhookEndpoint:
    def test_ping_returns_pong(self, client):
        payload = json.dumps({"zen": "test", "hook_id": 1}).encode()
        secret = "test-secret"
        sig = _make_sig(payload, secret)
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            resp = client.post(
                "/webhook/github",
                data=payload,
                content_type="application/json",
                headers={"X-GitHub-Event": "ping", "X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "pong"

    def test_push_event_calls_discord(self, client):
        import webhook as wh
        secret = "test-secret"
        sig = _make_sig(PUSH_PAYLOAD, secret)
        with patch.object(wh, "_send_discord_embed", return_value=True), \
             patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            resp = client.post(
                "/webhook/github",
                data=PUSH_PAYLOAD,
                content_type="application/json",
                headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig},
            )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"

    def test_invalid_signature_returns_403(self, client):
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": "real-secret"}):
            resp = client.post(
                "/webhook/github",
                data=PUSH_PAYLOAD,
                content_type="application/json",
                headers={
                    "X-GitHub-Event": "push",
                    "X-Hub-Signature-256": "sha256=badhash",
                },
            )
        assert resp.status_code == 403
        assert "signature mismatch" in resp.get_json()["error"]

    def test_valid_signature_passes(self, client):
        secret = "test-secret"
        sig = _make_sig(PUSH_PAYLOAD, secret)
        import webhook as wh
        with patch.dict(os.environ, {"GITHUB_WEBHOOK_SECRET": secret}):
            with patch.object(wh, "_send_discord_embed", return_value=True):
                resp = client.post(
                    "/webhook/github",
                    data=PUSH_PAYLOAD,
                    content_type="application/json",
                    headers={"X-GitHub-Event": "push", "X-Hub-Signature-256": sig},
                )
        assert resp.status_code == 200

    def test_logs_api_returns_list(self, client):
        resp = client.get("/api/logs")
        assert resp.status_code == 200
        assert isinstance(resp.get_json(), list)

    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
