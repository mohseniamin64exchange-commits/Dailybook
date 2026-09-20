"""Database models for DailyBook.

The models deliberately keep denormalised user snapshots on historical
records.  This means that soft-deleting or editing a user never changes the
identity shown on an old entry or audit event.
"""

from datetime import datetime, timezone
import json

from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash

from .extensions import db


def utc_now():
    """Return an aware UTC timestamp for all application-created timestamps."""
    return datetime.now(timezone.utc)


class TimestampMixin:
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )


class User(UserMixin, TimestampMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String(120), nullable=False)
    last_name = db.Column(db.String(120), nullable=False)
    username = db.Column(db.String(80), nullable=False, unique=True, index=True)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="user")
    # active, inactive, or deleted. Deleted is a soft-delete state.
    status = db.Column(db.String(20), nullable=False, default="active", index=True)
    failed_login_count = db.Column(db.Integer, nullable=False, default=0)
    is_locked = db.Column(db.Boolean, nullable=False, default=False)

    daily_entries = db.relationship(
        "DailyEntry", back_populates="created_by", foreign_keys="DailyEntry.created_by_user_id"
    )
    audit_logs = db.relationship("AuditLog", back_populates="actor", passive_deletes=True)

    @property
    def is_active(self):
        """Flask-Login compatibility, including the application's lock rules."""
        return self.status == "active" and not self.is_locked

    @property
    def is_deleted(self):
        return self.status == "deleted"

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def soft_delete(self):
        self.status = "deleted"
        self.is_locked = True

    def actor_snapshot(self):
        return {
            "first_name": self.first_name,
            "last_name": self.last_name,
            "username": self.username,
        }


class DailyEntry(TimestampMixin, db.Model):
    __tablename__ = "daily_entries"

    id = db.Column(db.Integer, primary_key=True)
    # Stored as Gregorian date; presentation converts it to Jalali.
    entry_date = db.Column(db.Date, nullable=False)
    entry_type = db.Column(db.String(10), nullable=False)  # expense / income
    description = db.Column(db.Text, nullable=False, default="")
    # Integer monetary unit only: no floating point or decimal values.
    amount = db.Column(db.Integer, nullable=False)
    deleted_at = db.Column(db.DateTime(timezone=True), nullable=True, index=True)
    created_by_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    created_by_first_name_snapshot = db.Column(db.String(120), nullable=False)
    created_by_last_name_snapshot = db.Column(db.String(120), nullable=False)
    created_by_username_snapshot = db.Column(db.String(80), nullable=False)

    created_by = db.relationship(
        "User", back_populates="daily_entries", foreign_keys=[created_by_user_id]
    )

    def snapshot(self):
        return {
            "id": self.id,
            "entry_date": self.entry_date.isoformat() if self.entry_date else None,
            "entry_type": self.entry_type,
            "description": self.description,
            "amount": self.amount,
            "created_by_user_id": self.created_by_user_id,
            "created_by_first_name_snapshot": self.created_by_first_name_snapshot,
            "created_by_last_name_snapshot": self.created_by_last_name_snapshot,
            "created_by_username_snapshot": self.created_by_username_snapshot,
        }


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)
    event_type = db.Column(db.String(80), nullable=False, index=True)
    actor_user_id = db.Column(
        db.Integer, db.ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    actor_name_snapshot = db.Column(db.String(255), nullable=True)
    actor_username_snapshot = db.Column(db.String(80), nullable=True)
    related_record_type = db.Column(db.String(80), nullable=True)
    related_record_id = db.Column(db.Integer, nullable=True, index=True)
    before_data = db.Column(db.Text, nullable=True)
    after_data = db.Column(db.Text, nullable=True)
    success = db.Column(db.Boolean, nullable=False, default=True, index=True)
    message = db.Column(db.Text, nullable=True)
    client_ip = db.Column(db.String(45), nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now, index=True)

    actor = db.relationship("User", back_populates="audit_logs", foreign_keys=[actor_user_id])

    @staticmethod
    def encode_data(value):
        if value is None or isinstance(value, str):
            return value
        return json.dumps(value, ensure_ascii=False, default=str, sort_keys=True)

    @staticmethod
    def decode_data(value):
        if value in (None, ""):
            return None
        try:
            return json.loads(value)
        except (TypeError, json.JSONDecodeError):
            return value

    @property
    def before(self):
        return self.decode_data(self.before_data)

    @property
    def after(self):
        return self.decode_data(self.after_data)


class Setting(db.Model):
    __tablename__ = "settings"

    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(120), nullable=False, unique=True, index=True)
    backup_path = db.Column(db.Text, nullable=True)
    auto_backup_enabled = db.Column(db.Boolean, nullable=False, default=True)
    value = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime(timezone=True), nullable=False, default=utc_now)
    updated_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=utc_now, onupdate=utc_now
    )
