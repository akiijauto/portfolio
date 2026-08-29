from datetime import datetime

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()

STATUSES = ["新規", "連絡済み", "商談中", "成約", "失注"]
SOURCES = ["ホームページ", "SNS", "紹介", "クラウドソーシング", "その他"]


class Inquiry(db.Model):
    __tablename__ = "inquiries"
    id = db.Column(db.Integer, primary_key=True)
    company = db.Column(db.String(100), nullable=False)
    contact_name = db.Column(db.String(100), default="")
    email = db.Column(db.String(255), default="")
    phone = db.Column(db.String(50), default="")
    source = db.Column(db.String(50), default="")
    content = db.Column(db.Text, default="")
    status = db.Column(db.String(20), default="新規")
    memo = db.Column(db.Text, default="")
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "company": self.company,
            "contact_name": self.contact_name,
            "email": self.email,
            "phone": self.phone,
            "source": self.source,
            "content": self.content,
            "status": self.status,
            "memo": self.memo,
            "created_at": self.created_at.strftime("%Y-%m-%d %H:%M"),
            "updated_at": self.updated_at.strftime("%Y-%m-%d %H:%M"),
        }
