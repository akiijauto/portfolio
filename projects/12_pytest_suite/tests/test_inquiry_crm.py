"""17_inquiry_crm のテスト（app.py エンドポイント + generator.py ロジック、インメモリDB）。"""
import sys
import importlib.util
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).parents[3]
PROJECT = ROOT / "projects" / "17_inquiry_crm"

sys.path.insert(0, str(PROJECT))
for _mod in ("generator", "models", "app"):
    sys.modules.pop(_mod, None)

spec = importlib.util.spec_from_file_location("crm_app", PROJECT / "app.py")
crm_app_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(crm_app_module)

flask_app = crm_app_module.app
db = crm_app_module.db
STATUSES = crm_app_module.STATUSES
SOURCES = crm_app_module.SOURCES
generator = crm_app_module.generator

flask_app.root_path = str(PROJECT)
flask_app.template_folder = str(PROJECT / "templates")
flask_app.static_folder = str(PROJECT / "static")


@pytest.fixture
def client():
    flask_app.config["TESTING"] = True
    flask_app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///:memory:"
    flask_app.config["WTF_CSRF_ENABLED"] = False

    with flask_app.app_context():
        db.drop_all()
        db.create_all()
        yield flask_app.test_client()
        db.drop_all()


# ── ヘルパー ──────────────────────────────────────────────────────

def _create_inquiry(client, **overrides):
    data = {
        "company": "テスト株式会社",
        "contact_name": "山田太郎",
        "email": "test@example.com",
        "phone": "090-1234-5678",
        "source": "ホームページ",
        "content": "問い合わせ内容です",
    }
    data.update(overrides)
    return client.post("/api/inquiries", data=data)


# ── / ────────────────────────────────────────────────────────────

class TestIndex:
    def test_index_returns_200(self, client):
        resp = client.get("/")
        assert resp.status_code == 200


# ── /api/stats ───────────────────────────────────────────────────

class TestStatsEndpoint:
    def test_empty_counts_all_zero(self, client):
        resp = client.get("/api/stats")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["total"] == 0
        assert all(v == 0 for v in data["counts"].values())

    def test_counts_reflect_created_inquiries(self, client):
        _create_inquiry(client)
        resp = client.get("/api/stats")
        data = resp.get_json()
        assert data["total"] == 1
        assert data["counts"]["新規"] == 1


# ── /api/inquiries (GET) ─────────────────────────────────────────

class TestListInquiries:
    def test_returns_all_inquiries(self, client):
        _create_inquiry(client, company="A社")
        _create_inquiry(client, company="B社")
        resp = client.get("/api/inquiries")
        assert resp.status_code == 200
        assert len(resp.get_json()["inquiries"]) == 2

    def test_filters_by_status(self, client):
        create_resp = _create_inquiry(client, company="A社")
        inquiry_id = create_resp.get_json()["inquiry"]["id"]
        client.post(f"/api/inquiries/{inquiry_id}/status", data={"status": "成約"})
        _create_inquiry(client, company="B社")

        resp = client.get("/api/inquiries?status=成約")
        data = resp.get_json()
        assert len(data["inquiries"]) == 1
        assert data["inquiries"][0]["company"] == "A社"


# ── /api/inquiries (POST) ────────────────────────────────────────

class TestCreateInquiry:
    def test_missing_company_returns_400(self, client):
        resp = _create_inquiry(client, company="")
        assert resp.status_code == 400

    def test_too_long_company_returns_400(self, client):
        resp = _create_inquiry(client, company="a" * 101)
        assert resp.status_code == 400

    def test_too_long_email_returns_400(self, client):
        resp = _create_inquiry(client, email="a" * 256)
        assert resp.status_code == 400

    def test_too_long_content_returns_400(self, client):
        resp = _create_inquiry(client, content="a" * 2001)
        assert resp.status_code == 400

    def test_invalid_source_falls_back_to_other(self, client):
        resp = _create_inquiry(client, source="Twitter")
        assert resp.status_code == 200
        assert resp.get_json()["inquiry"]["source"] == "その他"

    def test_success_creates_with_status_new(self, client):
        resp = _create_inquiry(client)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["inquiry"]["status"] == "新規"
        assert data["inquiry"]["company"] == "テスト株式会社"


# ── /api/inquiries/<id>/status ───────────────────────────────────

class TestUpdateStatus:
    def test_not_found_returns_404(self, client):
        resp = client.post("/api/inquiries/999/status", data={"status": "成約"})
        assert resp.status_code == 404

    def test_invalid_status_returns_400(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        resp = client.post(f"/api/inquiries/{inquiry_id}/status", data={"status": "不正な状態"})
        assert resp.status_code == 400

    def test_success_updates_status(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        resp = client.post(f"/api/inquiries/{inquiry_id}/status", data={"status": "商談中"})
        assert resp.status_code == 200
        assert resp.get_json()["inquiry"]["status"] == "商談中"


# ── /api/inquiries/<id>/memo ──────────────────────────────────────

class TestUpdateMemo:
    def test_not_found_returns_404(self, client):
        resp = client.post("/api/inquiries/999/memo", data={"memo": "メモ"})
        assert resp.status_code == 404

    def test_too_long_memo_returns_400(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        resp = client.post(f"/api/inquiries/{inquiry_id}/memo", data={"memo": "a" * 2001})
        assert resp.status_code == 400

    def test_success_updates_memo(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        resp = client.post(f"/api/inquiries/{inquiry_id}/memo", data={"memo": "対応済み"})
        assert resp.status_code == 200
        assert resp.get_json()["inquiry"]["memo"] == "対応済み"


# ── /api/inquiries/<id>/delete ────────────────────────────────────

class TestDeleteInquiry:
    def test_not_found_returns_404(self, client):
        resp = client.post("/api/inquiries/999/delete")
        assert resp.status_code == 404

    def test_success_deletes(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        resp = client.post(f"/api/inquiries/{inquiry_id}/delete")
        assert resp.status_code == 200
        assert client.get("/api/inquiries").get_json()["inquiries"] == []


# ── /reply_draft ──────────────────────────────────────────────────

class TestReplyDraft:
    def test_too_long_purpose_returns_400(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        resp = client.post("/reply_draft", data={
            "inquiry_id": str(inquiry_id), "purpose": "a" * 201,
        })
        assert resp.status_code == 400

    def test_no_inquiry_id_returns_400(self, client):
        resp = client.post("/reply_draft", data={"inquiry_id": "0"})
        assert resp.status_code == 400

    def test_nonexistent_inquiry_returns_400(self, client):
        resp = client.post("/reply_draft", data={"inquiry_id": "999"})
        assert resp.status_code == 400

    def test_invalid_tone_falls_back_to_default(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        with patch.object(generator, "generate_reply", return_value="返信文") as mock_gen:
            resp = client.post("/reply_draft", data={
                "inquiry_id": str(inquiry_id), "tone": "存在しないトーン",
            })
        assert resp.status_code == 200
        args, _ = mock_gen.call_args
        assert args[3] == "丁寧（標準）"

    def test_success_returns_draft(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        with patch.object(generator, "generate_reply", return_value="返信文面"):
            resp = client.post("/reply_draft", data={"inquiry_id": str(inquiry_id)})
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["ok"] is True
        assert data["draft"] == "返信文面"

    def test_generation_error_returns_500(self, client):
        inquiry_id = _create_inquiry(client).get_json()["inquiry"]["id"]
        with patch.object(generator, "generate_reply", side_effect=Exception("boom")):
            resp = client.post("/reply_draft", data={"inquiry_id": str(inquiry_id)})
        assert resp.status_code == 500


# ── generator.generate_reply() ───────────────────────────────────

def _mock_client_with_text(text):
    mock_client = MagicMock()
    mock_message = MagicMock()
    mock_message.content = [MagicMock(text=text)]
    mock_client.messages.create.return_value = mock_message
    return mock_client


class TestGenerateReply:
    def test_sender_includes_contact_name(self):
        mock_client = _mock_client_with_text("返信文")
        with patch.object(generator, "_client", return_value=mock_client):
            generator.generate_reply("テスト株式会社", "山田太郎", "内容", "丁寧（標準）")
        prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "テスト株式会社 山田太郎様" in prompt

    def test_sender_without_contact_name(self):
        mock_client = _mock_client_with_text("返信文")
        with patch.object(generator, "_client", return_value=mock_client):
            generator.generate_reply("テスト株式会社", "", "内容", "丁寧（標準）")
        prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "テスト株式会社様" in prompt

    def test_default_purpose_used_when_empty(self):
        mock_client = _mock_client_with_text("返信文")
        with patch.object(generator, "_client", return_value=mock_client):
            generator.generate_reply("テスト株式会社", "山田太郎", "内容", "丁寧（標準）", "")
        prompt = mock_client.messages.create.call_args.kwargs["messages"][0]["content"]
        assert "問い合わせへの感謝" in prompt

    def test_returns_stripped_text(self):
        mock_client = _mock_client_with_text("  返信本文  \n")
        with patch.object(generator, "_client", return_value=mock_client):
            result = generator.generate_reply("テスト株式会社", "山田太郎", "内容", "丁寧（標準）")
        assert result == "返信本文"
