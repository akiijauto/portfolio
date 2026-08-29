import io
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parents[3]))
sys.path.insert(0, str(Path(__file__).parents[1]))

import pytest
from app import create_app

SAMPLE_CSV = "month,sales\n1月,100\n2月,200\n3月,150\n".encode("utf-8")


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


def test_upload_rejects_non_csv(client):
    data = {"csv_file": (io.BytesIO(b"not a csv"), "data.txt")}
    res = client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert res.status_code == 200


def test_upload_then_preview_shown(client):
    data = {"csv_file": (io.BytesIO(SAMPLE_CSV), "data.csv")}
    res = client.post("/upload", data=data, content_type="multipart/form-data", follow_redirects=True)
    assert res.status_code == 200
    assert "データプレビュー".encode() in res.data


def test_ask_without_upload_redirects(client):
    res = client.post("/ask", data={"question": "売上は？"}, follow_redirects=True)
    assert res.status_code == 200


def test_ask_with_mocked_ai_returns_chart(client):
    data = {"csv_file": (io.BytesIO(SAMPLE_CSV), "data.csv")}
    client.post("/upload", data=data, content_type="multipart/form-data")

    fake_spec = {
        "groupby_column": "month",
        "value_column": "sales",
        "agg": "sum",
        "chart_type": "bar",
        "answer_summary": "2月が最も売上が高いです。",
    }
    with patch("app.call_claude_json", return_value=fake_spec):
        res = client.post("/ask", data={"question": "月別の売上は？"})
    assert res.status_code == 200
    assert "data:image/png;base64".encode() in res.data


def test_ask_rejects_unknown_column(client):
    data = {"csv_file": (io.BytesIO(SAMPLE_CSV), "data.csv")}
    client.post("/upload", data=data, content_type="multipart/form-data")

    fake_spec = {
        "groupby_column": "not_a_column",
        "value_column": "sales",
        "agg": "sum",
        "chart_type": "bar",
        "answer_summary": "",
    }
    with patch("app.call_claude_json", return_value=fake_spec):
        res = client.post("/ask", data={"question": "存在しない列で質問"})
    assert res.status_code == 200
    assert "分析に失敗しました".encode() in res.data
