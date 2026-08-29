from datetime import datetime, timezone

from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class Task(db.Model):
    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    line_user_id = db.Column(db.String(64), nullable=False)
    task_name = db.Column(db.String(200), nullable=False)
    due_date = db.Column(db.String(10), nullable=True)  # YYYY-MM-DD
    category = db.Column(db.String(50), nullable=False, default="その他")
    status = db.Column(db.String(20), nullable=False, default="未完了")
    reminder_sent = db.Column(db.Boolean, nullable=False, default=False)
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
