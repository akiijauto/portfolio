import sys
import os
from datetime import date, datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Blueprint, Flask, redirect, render_template, request, jsonify, url_for, flash
from flask_login import LoginManager, current_user, login_required, login_user, logout_user
from sqlalchemy import func

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf

from models import Category, Transaction, User, db

load_dotenv()

BASE_DIR = Path(__file__).parent

bp = Blueprint("budget_tracker", __name__, template_folder="templates", static_folder="static")

login_manager = LoginManager()
login_manager.login_view = "budget_tracker.login"


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ── 認証 ────────────────────────────────────────────────────────

@bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for(".index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        if not email or not password:
            flash("メールアドレスとパスワードを入力してください。")
            return render_template("register.html")
        if User.query.filter_by(email=email).first():
            flash("そのメールアドレスはすでに登録されています。")
            return render_template("register.html")
        user = User(email=email)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        # デフォルトカテゴリを作成
        defaults = [
            ("食費", "#f97316"), ("交通費", "#3b82f6"), ("娯楽", "#a855f7"),
            ("日用品", "#22c55e"), ("その他", "#94a3b8"),
        ]
        for name, color in defaults:
            db.session.add(Category(user_id=user.id, name=name, color=color))
        db.session.commit()
        login_user(user)
        return redirect(url_for(".index"))
    return render_template("register.html")


@bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for(".index"))
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        password = request.form.get("password", "")
        user = User.query.filter_by(email=email).first()
        if not user or not user.check_password(password):
            flash("メールアドレスまたはパスワードが正しくありません。")
            return render_template("login.html")
        login_user(user)
        return redirect(url_for(".index"))
    return render_template("login.html")


@bp.route("/logout", methods=["POST"])
@login_required
def logout():
    logout_user()
    return redirect(url_for(".login"))


# ── ダッシュボード ───────────────────────────────────────────────

@bp.route("/")
@login_required
def index():
    today = date.today()
    # 当月合計
    monthly_total = db.session.query(func.sum(Transaction.amount)).filter(
        Transaction.user_id == current_user.id,
        func.strftime("%Y-%m", Transaction.date) == today.strftime("%Y-%m"),
    ).scalar() or 0

    # 最新20件
    recent = (
        Transaction.query
        .filter_by(user_id=current_user.id)
        .order_by(Transaction.date.desc(), Transaction.created_at.desc())
        .limit(20)
        .all()
    )

    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
    return render_template("index.html", monthly_total=monthly_total, recent=recent, categories=categories, today=today)


# ── 収支 ────────────────────────────────────────────────────────

@bp.route("/transactions/new", methods=["GET", "POST"])
@login_required
def transaction_new():
    categories = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
    if request.method == "POST":
        try:
            amount = int(request.form.get("amount", 0))
            if amount <= 0:
                raise ValueError
        except ValueError:
            flash("金額は1以上の整数を入力してください。")
            return render_template("transaction_form.html", categories=categories, today=date.today())

        cat_id = int(request.form.get("category_id", 0))
        cat = Category.query.filter_by(id=cat_id, user_id=current_user.id).first()
        if not cat:
            flash("カテゴリを選択してください。")
            return render_template("transaction_form.html", categories=categories, today=date.today())

        date_str = request.form.get("date", "")
        try:
            tx_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            tx_date = date.today()

        memo = request.form.get("memo", "").strip()[:200]
        tx = Transaction(
            user_id=current_user.id,
            category_id=cat.id,
            amount=amount,
            date=tx_date,
            memo=memo,
        )
        db.session.add(tx)
        db.session.commit()
        return redirect(url_for(".index"))

    return render_template("transaction_form.html", categories=categories, today=date.today())


@bp.route("/transactions/<int:tx_id>/delete", methods=["POST"])
@login_required
def transaction_delete(tx_id):
    tx = Transaction.query.filter_by(id=tx_id, user_id=current_user.id).first_or_404()
    db.session.delete(tx)
    db.session.commit()
    return redirect(url_for(".index"))


# ── カテゴリ ─────────────────────────────────────────────────────

@bp.route("/categories", methods=["GET", "POST"])
@login_required
def categories():
    if request.method == "POST":
        name = request.form.get("name", "").strip()[:50]
        color = request.form.get("color", "#6366f1")
        if name:
            db.session.add(Category(user_id=current_user.id, name=name, color=color))
            db.session.commit()
        return redirect(url_for(".categories"))
    cats = Category.query.filter_by(user_id=current_user.id).order_by(Category.name).all()
    return render_template("categories.html", categories=cats)


@bp.route("/categories/<int:cat_id>/delete", methods=["POST"])
@login_required
def category_delete(cat_id):
    cat = Category.query.filter_by(id=cat_id, user_id=current_user.id).first_or_404()
    db.session.delete(cat)
    db.session.commit()
    return redirect(url_for(".categories"))


# ── Chart.js API ─────────────────────────────────────────────────

@bp.route("/api/chart/donut")
@login_required
def api_donut():
    """当月のカテゴリ別支出 JSON。"""
    today = date.today()
    rows = (
        db.session.query(Category.name, Category.color, func.sum(Transaction.amount))
        .join(Transaction, Transaction.category_id == Category.id)
        .filter(
            Transaction.user_id == current_user.id,
            func.strftime("%Y-%m", Transaction.date) == today.strftime("%Y-%m"),
        )
        .group_by(Category.id)
        .all()
    )
    return jsonify({
        "labels": [r[0] for r in rows],
        "colors": [r[1] for r in rows],
        "data": [r[2] for r in rows],
    })


@bp.route("/api/chart/bar")
@login_required
def api_bar():
    """直近6ヶ月の月別合計支出 JSON。"""
    rows = (
        db.session.query(
            func.strftime("%Y-%m", Transaction.date).label("month"),
            func.sum(Transaction.amount).label("total"),
        )
        .filter(Transaction.user_id == current_user.id)
        .group_by("month")
        .order_by("month")
        .limit(6)
        .all()
    )
    return jsonify({
        "labels": [r[0] for r in rows],
        "data": [r[1] for r in rows],
    })


def create_app():
    app = Flask(__name__)
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", os.urandom(24).hex())
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'budget.db'}"
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
    app.run(debug=False, port=5010)
