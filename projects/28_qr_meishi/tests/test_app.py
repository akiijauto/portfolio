import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from app import create_app, _build_vcard


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
    assert "QRコード名刺メーカー".encode() in res.data


def test_generate_requires_name(client):
    res = client.post("/generate", data={"name": ""}, follow_redirects=True)
    assert res.status_code == 200


def test_generate_returns_pdf(client):
    res = client.post("/generate", data={
        "name": "山田太郎",
        "title": "エンジニア",
        "company": "テスト株式会社",
        "email": "yamada@example.com",
        "phone": "090-1234-5678",
        "url": "https://example.com",
    })
    assert res.status_code == 200
    assert res.mimetype == "application/pdf"


def test_build_vcard_includes_fields():
    vcard = _build_vcard("山田太郎", "エンジニア", "テスト株式会社", "a@example.com", "090", "https://example.com")
    assert "FN:山田太郎" in vcard
    assert "ORG:テスト株式会社" in vcard
    assert "BEGIN:VCARD" in vcard
