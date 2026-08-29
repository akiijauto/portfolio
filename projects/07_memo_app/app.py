import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, redirect, url_for, flash, abort
from flask_login import (
    LoginManager,
    login_user,
    logout_user,
    login_required,
    current_user,
)

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf

from models import db, User, Memo

load_dotenv()

BASE_DIR = Path(__file__).parent

bp = Blueprint("memo_app", __name__, template_folder="templates", static_folder="static")

login_manager = LoginManager()
login_manager.login_view = "memo_app.login"
login_manager.login_message = "ログインしてください。"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


@bp.route("/")
def index():
    if current_user.is_authenticated:
        return redirect(url_for(".memo_list"))
    return redirect(url_for(".login"))


@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(".memo_list"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if not email or not password:
            flash("メールアドレスとパスワードを入力してください。", "error")
        elif password != password_confirm:
            flash("パスワードが一致しません。", "error")
        elif len(password) < 8:
            flash("パスワードは8文字以上で設定してください。", "error")
        elif User.query.filter_by(email=email).first() is not None:
            flash("そのメールアドレスは既に登録されています。", "error")
        else:
            user = User(email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.commit()
            flash("登録が完了しました。ログインしてください。", "success")
            return redirect(url_for(".login"))

    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(".memo_list"))

    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")

        user = User.query.filter_by(email=email).first()
        if user is not None and user.check_password(password):
            login_user(user)
            return redirect(url_for(".memo_list"))

        flash("メールアドレスまたはパスワードが正しくありません。", "error")

    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for(".login"))


@bp.route("/memos")
@login_required
def memo_list():
    memos = (
        Memo.query.filter_by(user_id=current_user.id)
        .order_by(Memo.updated_at.desc())
        .all()
    )
    return render_template("memo_list.html", memos=memos)


@bp.route("/memos/new", methods=["GET", "POST"])
@login_required
def memo_new():
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()

        if not title:
            flash("タイトルを入力してください。", "error")
            return render_template("memo_form.html", memo=None, title=title, body=body)

        memo = Memo(user_id=current_user.id, title=title, body=body)
        db.session.add(memo)
        db.session.commit()
        flash("メモを作成しました。", "success")
        return redirect(url_for(".memo_list"))

    return render_template("memo_form.html", memo=None, title="", body="")


def _get_own_memo_or_404(memo_id):
    memo = db.session.get(Memo, memo_id)
    if memo is None:
        abort(404)
    if memo.user_id != current_user.id:
        abort(404)
    return memo


@bp.route("/memos/<int:memo_id>/edit", methods=["GET", "POST"])
@login_required
def memo_edit(memo_id):
    memo = _get_own_memo_or_404(memo_id)

    if request.method == "POST":
        title = request.form.get("title", "").strip()
        body = request.form.get("body", "").strip()

        if not title:
            flash("タイトルを入力してください。", "error")
            return render_template("memo_form.html", memo=memo, title=title, body=body)

        memo.title = title
        memo.body = body
        db.session.commit()
        flash("メモを更新しました。", "success")
        return redirect(url_for(".memo_list"))

    return render_template("memo_form.html", memo=memo, title=memo.title, body=memo.body)


@bp.route("/memos/<int:memo_id>/delete", methods=["POST"])
@login_required
def memo_delete(memo_id):
    memo = _get_own_memo_or_404(memo_id)
    db.session.delete(memo)
    db.session.commit()
    flash("メモを削除しました。", "success")
    return redirect(url_for(".memo_list"))


@bp.route("/portfolio")
def portfolio():
    return redirect("https://ai-labo.space/", code=301)


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'memo_app.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SESSION_COOKIE_HTTPONLY"] = True
    app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
    app.config["SESSION_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"
    app.config["REMEMBER_COOKIE_HTTPONLY"] = True
    app.config["REMEMBER_COOKIE_SECURE"] = os.environ.get("FLASK_ENV") == "production"

    init_csrf(app)
    db.init_app(app)
    login_manager.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5007)
