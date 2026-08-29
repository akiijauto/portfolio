import sys
import os
import logging
from pathlib import Path
from dotenv import load_dotenv
from flask import Blueprint, Flask, render_template, request, jsonify
import generator
from models import db, Inquiry, STATUSES, SOURCES

sys.path.insert(0, str(Path(__file__).parents[2]))
from shared.csrf_setup import init_csrf
from shared.errors import get as err
from shared.utils import handle_ai_error

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()
BASE_DIR = Path(__file__).parent

bp = Blueprint("inquiry_crm", __name__, template_folder="templates", static_folder="static")


@bp.route("/")
def index():
    return render_template(
        "index.html",
        statuses=STATUSES,
        sources=SOURCES,
        reply_tones=list(generator.REPLY_TONES.keys()),
    )


@bp.route("/api/stats")
def stats():
    counts = {s: Inquiry.query.filter_by(status=s).count() for s in STATUSES}
    total = sum(counts.values())
    return jsonify({"ok": True, "counts": counts, "total": total})


@bp.route("/api/inquiries", methods=["GET"])
def list_inquiries():
    status_filter = request.args.get("status", "")
    q = Inquiry.query
    if status_filter and status_filter in STATUSES:
        q = q.filter_by(status=status_filter)
    inquiries = q.order_by(Inquiry.created_at.desc()).all()
    return jsonify({"ok": True, "inquiries": [i.to_dict() for i in inquiries]})


@bp.route("/api/inquiries", methods=["POST"])
def create_inquiry():
    company = request.form.get("company", "").strip()
    contact_name = request.form.get("contact_name", "").strip()
    email = request.form.get("email", "").strip()
    phone = request.form.get("phone", "").strip()
    source = request.form.get("source", "").strip()
    content = request.form.get("content", "").strip()

    if not company:
        return jsonify({"ok": False, "error": "会社名・お名前は必須です"}), 400
    if (len(company) > 100 or len(contact_name) > 100 or len(email) > 255
            or len(phone) > 50 or len(source) > 50 or len(content) > 2000):
        return jsonify({"ok": False, "error": "入力が長すぎます"}), 400
    if source and source not in SOURCES:
        source = "その他"

    inquiry = Inquiry(
        company=company, contact_name=contact_name, email=email,
        phone=phone, source=source, content=content, status="新規",
    )
    db.session.add(inquiry)
    db.session.commit()
    return jsonify({"ok": True, "inquiry": inquiry.to_dict()})


@bp.route("/api/inquiries/<int:inquiry_id>/status", methods=["POST"])
def update_status(inquiry_id):
    inquiry = db.session.get(Inquiry, inquiry_id)
    if not inquiry:
        return jsonify({"ok": False, "error": "案件が見つかりません"}), 404
    status = request.form.get("status", "")
    if status not in STATUSES:
        return jsonify({"ok": False, "error": "不正なステータスです"}), 400
    inquiry.status = status
    db.session.commit()
    return jsonify({"ok": True, "inquiry": inquiry.to_dict()})


@bp.route("/api/inquiries/<int:inquiry_id>/memo", methods=["POST"])
def update_memo(inquiry_id):
    inquiry = db.session.get(Inquiry, inquiry_id)
    if not inquiry:
        return jsonify({"ok": False, "error": "案件が見つかりません"}), 404
    memo = request.form.get("memo", "").strip()
    if len(memo) > 2000:
        return jsonify({"ok": False, "error": "入力が長すぎます"}), 400
    inquiry.memo = memo
    db.session.commit()
    return jsonify({"ok": True, "inquiry": inquiry.to_dict()})


@bp.route("/api/inquiries/<int:inquiry_id>/delete", methods=["POST"])
def delete_inquiry(inquiry_id):
    inquiry = db.session.get(Inquiry, inquiry_id)
    if not inquiry:
        return jsonify({"ok": False, "error": "案件が見つかりません"}), 404
    db.session.delete(inquiry)
    db.session.commit()
    return jsonify({"ok": True})


@bp.route("/reply_draft", methods=["POST"])
def reply_draft():
    try:
        inquiry_id = int(request.form.get("inquiry_id", "0"))
    except ValueError:
        inquiry_id = 0
    tone = request.form.get("tone", "丁寧（標準）")
    purpose = request.form.get("purpose", "").strip()

    if len(purpose) > 200:
        return jsonify({"ok": False, "error": "入力が長すぎます"}), 400

    inquiry = db.session.get(Inquiry, inquiry_id) if inquiry_id else None
    if not inquiry:
        return jsonify({"ok": False, "error": "案件を選択してください"}), 400
    if tone not in generator.REPLY_TONES:
        tone = "丁寧（標準）"

    try:
        draft = generator.generate_reply(
            inquiry.company, inquiry.contact_name, inquiry.content, tone, purpose
        )
        return jsonify({"ok": True, "draft": draft})
    except Exception as e:
        logger.exception("reply draft generation failed")
        return jsonify({"ok": False, "error": handle_ai_error(e, "inquiry-crm")}), 500


def create_app():
    app = Flask(__name__)
    app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{BASE_DIR / 'inquiries.db'}"
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    init_csrf(app)
    db.init_app(app)
    app.register_blueprint(bp)

    with app.app_context():
        db.create_all()

    return app


app = create_app()

if __name__ == "__main__":
    app.run(debug=False, port=5017)
