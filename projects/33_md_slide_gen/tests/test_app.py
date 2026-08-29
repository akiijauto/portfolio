import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from app import create_app, _split_slides, _parse_slide


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


def test_preview_requires_markdown(client):
    res = client.post("/preview", data={"markdown": ""}, follow_redirects=True)
    assert res.status_code == 200


def test_preview_renders_markdown(client):
    res = client.post("/preview", data={"markdown": "# タイトル\n- 項目1", "theme": "blue"})
    assert res.status_code == 200
    assert "タイトル".encode() in res.data


def test_export_pptx_returns_file(client):
    res = client.post("/export/pptx", data={
        "markdown": "# 1枚目\n- A\n- B\n\n---\n\n# 2枚目\n- C",
        "theme": "green",
    })
    assert res.status_code == 200
    assert res.mimetype == "application/vnd.openxmlformats-officedocument.presentationml.presentation"


def test_split_slides_separates_by_dashes():
    slides = _split_slides("# A\n- x\n\n---\n\n# B\n- y")
    assert len(slides) == 2


def test_parse_slide_extracts_title_and_bullets():
    title, bullets = _parse_slide("# タイトル\n- 項目1\n- 項目2")
    assert title == "タイトル"
    assert bullets == ["項目1", "項目2"]
