"""
Flask-WTF CSRFを簡単にセットアップするヘルパー（Vercelデプロイ用に shared/csrf_setup.py を複製）。

使い方:
    from _shared.csrf_setup import init_csrf
    app = Flask(__name__)
    init_csrf(app)
"""
import os
from flask_wtf.csrf import CSRFProtect

_csrf = CSRFProtect()

def init_csrf(app):
    """アプリにCSRF保護を追加する。SECRET_KEYが未設定の場合は自動生成する。"""
    if not app.config.get("SECRET_KEY"):
        app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    # モバイルブラウザ等でRefererヘッダーが送信されない場合に
    # 「The referrer header is missing.」でCSRF検証が失敗するのを防ぐ
    app.config.setdefault("WTF_CSRF_SSL_STRICT", False)
    _csrf.init_app(app)
    return _csrf
