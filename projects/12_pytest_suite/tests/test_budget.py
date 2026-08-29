"""10_budget_tracker の Flask + SQLAlchemy テスト（インメモリDB）。"""
import importlib.util
import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[3]
PROJECT = ROOT / "projects" / "10_budget_tracker"

# ── モジュールロード（DB URI をインメモリに差し替えてから exec）──────────────

os.environ.setdefault("SECRET_KEY", "test-secret")

# 17_inquiry_crm にも models.py が存在するため、本プロジェクトを sys.path 先頭に
# 入れてキャッシュをクリアしてから読み込む（モジュール名衝突対策）
sys.path.insert(0, str(PROJECT))
for _mod in ("models", "app"):
    sys.modules.pop(_mod, None)

spec = importlib.util.spec_from_file_location("budget_app", PROJECT / "app.py")
budget_module = importlib.util.module_from_spec(spec)

# exec 前に URI を差し替えるため、flask が先にインポートされる必要がある
# → ここでは exec してから override する（create_all は fixture 内で再実行）
spec.loader.exec_module(budget_module)

flask_app = budget_module.app
db = budget_module.db
User = budget_module.User
Category = budget_module.Category
Transaction = budget_module.Transaction

# テンプレート・スタティックパスをプロジェクトルートに固定
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

def _register(client, email="test@test.com", password="password"):
    return client.post("/register", data={"email": email, "password": password},
                       follow_redirects=True)


def _login(client, email="test@test.com", password="password"):
    return client.post("/login", data={"email": email, "password": password},
                       follow_redirects=True)


def _add_transaction(client, amount, category_id, date="2026-06-01", memo=""):
    return client.post("/transactions/new", data={
        "amount": amount, "category_id": category_id,
        "date": date, "memo": memo,
    }, follow_redirects=True)


# ── 認証テスト ────────────────────────────────────────────────────

class TestAuth:
    def test_register_creates_user(self, client):
        _register(client)
        with flask_app.app_context():
            assert User.query.filter_by(email="test@test.com").first() is not None

    def test_register_creates_default_categories(self, client):
        _register(client)
        with flask_app.app_context():
            user = User.query.filter_by(email="test@test.com").first()
            assert len(user.categories) == 5

    def test_duplicate_email_shows_error(self, client):
        _register(client)
        # ログアウトしてから同じメールで再登録
        client.post("/logout", data={})
        resp = _register(client)
        assert "すでに登録" in resp.data.decode("utf-8")

    def test_login_success_shows_dashboard(self, client):
        _register(client)
        client.post("/logout", data={})
        resp = _login(client)
        assert "ダッシュボード" in resp.data.decode("utf-8")

    def test_wrong_password_shows_error(self, client):
        _register(client)
        client.post("/logout", data={})
        resp = client.post("/login", data={"email": "test@test.com", "password": "wrong"},
                           follow_redirects=True)
        assert "正しくありません" in resp.data.decode("utf-8")

    def test_unauthenticated_redirects_to_login(self, client):
        resp = client.get("/", follow_redirects=False)
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]


# ── 収支テスト ────────────────────────────────────────────────────

class TestTransactions:
    def _setup_user(self, client):
        _register(client)
        with flask_app.app_context():
            user = User.query.filter_by(email="test@test.com").first()
            return user.categories[0].id

    def test_add_transaction_appears_in_dashboard(self, client):
        cat_id = self._setup_user(client)
        resp = _add_transaction(client, 1500, cat_id, "2026-06-01", "ランチ")
        assert resp.status_code == 200
        assert "1,500" in resp.data.decode("utf-8")

    def test_invalid_amount_shows_error(self, client):
        self._setup_user(client)
        resp = client.post("/transactions/new", data={
            "amount": -100, "category_id": 1, "date": "2026-06-01"
        }, follow_redirects=True)
        assert "1以上" in resp.data.decode("utf-8")

    def test_delete_transaction(self, client):
        cat_id = self._setup_user(client)
        _add_transaction(client, 500, cat_id)
        with flask_app.app_context():
            tx = Transaction.query.first()
            tx_id = tx.id

        resp = client.post(f"/transactions/{tx_id}/delete", follow_redirects=True)
        assert resp.status_code == 200
        with flask_app.app_context():
            assert db.session.get(Transaction, tx_id) is None

    def test_other_user_cannot_delete(self, client):
        """ユーザーAの収支をユーザーBは削除できない（404）。"""
        _register(client, "user_a@test.com")
        with flask_app.app_context():
            ua = User.query.filter_by(email="user_a@test.com").first()
            cat_id = ua.categories[0].id

        _add_transaction(client, 999, cat_id)
        with flask_app.app_context():
            tx = Transaction.query.first()
            tx_id = tx.id

        # 同じクライアントでユーザーBにスイッチ
        client.post("/logout", data={})
        _register(client, "user_b@test.com")
        resp = client.post(f"/transactions/{tx_id}/delete")
        assert resp.status_code == 404


# ── Chart.js API テスト ───────────────────────────────────────────

class TestChartAPI:
    def test_donut_api_returns_json_structure(self, client):
        _register(client)
        resp = client.get("/api/chart/donut")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "labels" in data
        assert "data" in data
        assert "colors" in data

    def test_bar_api_returns_json_structure(self, client):
        _register(client)
        resp = client.get("/api/chart/bar")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "labels" in data
        assert "data" in data

    def test_donut_reflects_transactions(self, client):
        _register(client)
        with flask_app.app_context():
            user = User.query.filter_by(email="test@test.com").first()
            cat_id = user.categories[0].id

        _add_transaction(client, 3000, cat_id, "2026-06-01")
        resp = client.get("/api/chart/donut")
        data = resp.get_json()
        assert 3000 in data["data"]
