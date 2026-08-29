import io
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from PIL import Image, ImageDraw
from app import create_app


@pytest.fixture
def client():
    app = create_app()
    app.config["TESTING"] = True
    app.config["WTF_CSRF_ENABLED"] = False
    with app.test_client() as client:
        yield client


def _make_text_image(text: str) -> bytes:
    image = Image.new("RGB", (300, 80), "white")
    draw = ImageDraw.Draw(image)
    draw.text((10, 25), text, fill="black")
    buf = io.BytesIO()
    image.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


def test_index_ok(client):
    res = client.get("/")
    assert res.status_code == 200


def test_ocr_rejects_unsupported_extension(client):
    data = {"image_file": (io.BytesIO(b"dummy"), "data.txt")}
    res = client.post("/ocr", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert res.status_code == 200


def test_ocr_with_mocked_engine_and_ai(client):
    image_bytes = _make_text_image("HELLO")
    data = {
        "image_file": (io.BytesIO(image_bytes), "photo.png"),
        "proofread": "on",
    }
    with patch("app._ocr_image", return_value="HELLO（誤字あり）"), \
         patch("app.call_claude_text", return_value="HELLO"), \
         patch.dict("os.environ", {"GEMINI_API_KEY": "dummy"}):
        res = client.post("/ocr", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    assert "HELLO".encode() in res.data


def test_ocr_without_proofread_keeps_raw_text(client):
    image_bytes = _make_text_image("HELLO")
    data = {"image_file": (io.BytesIO(image_bytes), "photo.png")}
    with patch("app._ocr_image", return_value="RAW TEXT"):
        res = client.post("/ocr", data=data, content_type="multipart/form-data")
    assert res.status_code == 200
    assert "RAW TEXT".encode() in res.data


def test_download_returns_txt(client):
    res = client.post("/download", data={"text": "サンプルテキスト"})
    assert res.status_code == 200
    assert res.mimetype == "text/plain"
    assert "attachment" in res.headers["Content-Disposition"]
