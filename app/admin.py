"""Administrator-only views: users, reports, audit log and backups."""
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from functools import wraps
from pathlib import Path

from flask import Blueprint, current_app, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required
from werkzeug.security import generate_password_hash

from .extensions import db
from .services.backup import create_backup
from .server_config import (
    configure_windows_firewall,
    configure_windows_service_autostart,
    schedule_windows_service_restart,
    validate_port,
)
from .utils import format_amount, gregorian_to_jalali, jalali_to_gregorian_iso

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


_AUDIT_FIELD_LABELS = {
    "id": "شناسه", "entry_date": "تاریخ", "entry_type": "نوع",
    "description": "شرح", "amount": "مبلغ", "created_by_user_id": "کاربر",
    "first_name": "نام", "last_name": "نام خانوادگی", "username": "نام کاربری",
    "role": "نقش", "is_active": "وضعیت", "backup_path": "مسیر پشتیبان",
    "auto_backup_enabled": "پشتیبان‌گیری خودکار", "server_port": "پورت سرور",
    "windows_autostart_enabled": "اجرای خودکار پس از روشن شدن ویندوز",
    "path": "مسیر",
}


def _audit_value_fa(key, value):
    if key == "entry_type":
        return {"income": "درآمد", "expense": "هزینه"}.get(str(value), str(value))
    if key in {"is_active", "auto_backup_enabled"}:
        return "فعال" if bool(value) else "غیرفعال"
    if key == "role":
        return {"admin": "مدیر", "user": "کاربر"}.get(str(value).lower(), str(value))
    if value is None:
        return "—"
    return str(value)


def _audit_data_fa(raw):
    """Turn stored technical JSON snapshots into short Persian display text."""
    if not raw:
        return ""
    try:
        data = json.loads(raw) if isinstance(raw, str) else raw
    except (TypeError, json.JSONDecodeError):
        return str(raw)
    if not isinstance(data, dict):
        return str(data)
    parts = []
    for key, value in data.items():
        # Internal ownership IDs are useful in storage but noisy in the UI.
        if key == "created_by_user_id":
            continue
        label = _AUDIT_FIELD_LABELS.get(key, key.replace("_", " "))
        parts.append(f"{label}: {_audit_value_fa(key, value)}")
    return "، ".join(parts)


def _audit_details_fa(log):
    before = _audit_data_fa(log.before_data)
    after = _audit_data_fa(log.after_data)
    message = (log.message or "").strip()
    chunks = []
    if message:
        chunks.append(message)
    if before and after:
        chunks.append(f"قبل: {before} ← بعد: {after}")
    elif before:
        chunks.append(f"اطلاعات قبلی: {before}")
    elif after:
        chunks.append(f"اطلاعات: {after}")
    return " | ".join(chunks) or "—"


def _related_record_fa(log):
    labels = {"DailyEntry": "ثبت روزانه", "User": "کاربر", "Setting": "تنظیمات"}
    label = labels.get(log.related_record_type, "")
    if log.related_record_id:
        return f"{label or 'رکورد'} شماره {log.related_record_id}"
    return label or "—"


def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if getattr(current_user, "role", "") not in ("admin", "Admin", "ADMIN"):
            flash("دسترسی فقط برای ادمین مجاز است.", "error")
            return redirect(url_for("entries.dashboard"))
        return view(*args, **kwargs)
    return wrapped


def _model(name):
    from . import models
    return getattr(models, name)


def _snapshot(user):
    return {"first_name": getattr(user, "first_name", ""), "last_name": getattr(user, "last_name", ""),
            "username": getattr(user, "username", "")}


def _log(event, message, success=True, related_id=None, before=None, after=None):
    try:
        AuditLog = _model("AuditLog")
        actor = current_user if getattr(current_user, "is_authenticated", False) else None
        snap = _snapshot(actor) if actor else {}
        data = dict(event_type=event, message=message, success=success,
                    actor_user_id=getattr(actor, "id", None),
                    actor_name_snapshot=(f"{snap.get('first_name', '')} {snap.get('last_name', '')}").strip(),
                    actor_username_snapshot=snap.get("username"), related_record_id=related_id,
                    before_data=json.dumps(before, ensure_ascii=False, default=str) if before else None,
                    after_data=json.dumps(after, ensure_ascii=False, default=str) if after else None,
                    client_ip=request.remote_addr, created_at=datetime.now(timezone.utc))
        db.session.add(AuditLog(**{k: v for k, v in data.items() if hasattr(AuditLog, k)}))
    except Exception:
        current_app.logger.exception("Unable to write audit log")


@admin_bp.get("/")
@admin_required
def dashboard():
    return redirect(url_for("admin.report"))


@admin_bp.route("/settings", methods=["GET", "POST"])
@admin_required
def settings():
    Setting = _model("Setting")
    port_setting = Setting.query.filter_by(key="server_port").first()
    if port_setting is None:
        port_setting = Setting(key="server_port", value=str(current_app.config.get("DEFAULT_PORT", 4000)))
        db.session.add(port_setting)
    autostart_setting = Setting.query.filter_by(key="windows_autostart_enabled").first()
    if autostart_setting is None:
        autostart_setting = Setting(key="windows_autostart_enabled", value="1")
        db.session.add(autostart_setting)
    db.session.commit()

    if request.method == "POST":
        try:
            port = validate_port(request.form.get("server_port"))
        except ValueError as exc:
            flash(str(exc), "error")
            return redirect(url_for("admin.settings"))

        autostart_enabled = request.form.get("windows_autostart_enabled") == "on"
        before = {
            "server_port": port_setting.value,
            "windows_autostart_enabled": autostart_setting.value == "1",
        }
        try:
            configure_windows_firewall(port)
            configure_windows_service_autostart(autostart_enabled)
        except OSError as exc:
            _log("server_settings_change_failed", str(exc), success=False, before=before,
                 after={"server_port": str(port), "windows_autostart_enabled": autostart_enabled})
            db.session.commit()
            flash(f"تنظیمات ذخیره نشد: {exc}", "error")
            return redirect(url_for("admin.settings"))

        port_changed = port_setting.value != str(port)
        port_setting.value = str(port)
        autostart_setting.value = "1" if autostart_enabled else "0"
        _log("server_settings_changed", "تنظیمات سرور تغییر کرد", before=before,
             after={"server_port": port_setting.value, "windows_autostart_enabled": autostart_enabled})
        db.session.commit()

        restarted = schedule_windows_service_restart() if port_changed else False
        if restarted:
            flash(f"تنظیمات ذخیره شد؛ سرویس با پورت {port} تا چند ثانیه دیگر راه‌اندازی مجدد می‌شود.", "success")
        else:
            flash("تنظیمات ذخیره شد.", "success")
        return redirect(url_for("admin.settings"))

    return render_template(
        "admin/settings.html",
        server_port=port_setting.value,
        windows_autostart_enabled=autostart_setting.value != "0",
        environment_override=bool(os.environ.get("DAILYBOOK_PORT")),
    )


@admin_bp.route("/users", methods=["GET", "POST"])
@admin_required
def users():
    User = _model("User")
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        if not username or len(username) < 3 or len(password) < 8:
            flash("نام کاربری حداقل ۳ و رمز عبور حداقل ۸ نویسه باشد.", "error")
            return redirect(url_for("admin.users"))
        if User.query.filter_by(username=username).first():
            flash("نام کاربری تکراری است.", "error")
        else:
            user = User(first_name=request.form.get("first_name", "").strip(), last_name=request.form.get("last_name", "").strip(),
                        username=username, password_hash=generate_password_hash(password),
                        role="user", status="active")
            db.session.add(user); db.session.flush()
            _log("user_created", "کاربر ایجاد شد", related_id=user.id, after=_snapshot(user)); db.session.commit()
            flash("کاربر ایجاد شد.", "success")
        return redirect(url_for("admin.users"))
    return render_template("admin/users.html", users=User.query.order_by(User.id.desc()).all())


@admin_bp.post("/users/<int:user_id>/<action>")
@admin_required
def user_action(user_id, action):
    User = _model("User"); user = db.session.get(User, user_id)
    if not user:
        flash("کاربر پیدا نشد.", "error"); return redirect(url_for("admin.users"))
    if user.id == current_user.id and action in {"deactivate", "delete"}:
        flash("مدیر نمی‌تواند حساب فعال خودش را غیرفعال یا حذف کند.", "error")
        return redirect(url_for("admin.users"))
    before = _snapshot(user) | {"status": user.status, "is_locked": user.is_locked}
    if action == "edit":
        first_name = request.form.get("first_name", "").strip()
        last_name = request.form.get("last_name", "").strip()
        username = request.form.get("username", "").strip()
        duplicate = User.query.filter(User.username == username, User.id != user.id).first()
        if not first_name or not last_name or len(username) < 3 or duplicate:
            flash("مشخصات نامعتبر است یا نام کاربری تکراری است.", "error")
            return redirect(url_for("admin.users"))
        user.first_name, user.last_name, user.username = first_name, last_name, username
    elif action == "activate": user.status = "active"
    elif action == "deactivate": user.status = "inactive"
    elif action == "unlock":
        user.is_locked = False; user.failed_login_count = 0
        if user.status == "locked": user.status = "active"
    elif action == "reset-password":
        password = request.form.get("password", "")
        if len(password) < 8:
            flash("رمز عبور حداقل ۸ نویسه باشد.", "error")
            return redirect(url_for("admin.users"))
        user.password_hash = generate_password_hash(password)
    elif action == "delete": user.soft_delete()
    else: flash("عملیات نامعتبر است.", "error"); return redirect(url_for("admin.users"))
    after = _snapshot(user) | {"status": user.status, "is_locked": user.is_locked}
    _log(f"user_{action.replace('-', '_')}", f"عملیات {action} روی کاربر انجام شد",
         related_id=user.id, before=before, after=after)
    db.session.commit(); flash("عملیات با موفقیت انجام شد.", "success")
    return redirect(url_for("admin.users"))


@admin_bp.get("/report")
@admin_required
def report():
    Entry = _model("DailyEntry")
    query = Entry.query.filter(Entry.deleted_at.is_(None))
    start, end = request.args.get("start"), request.args.get("end")
    try:
        if start: query = query.filter(Entry.entry_date >= date.fromisoformat(jalali_to_gregorian_iso(start)))
        if end: query = query.filter(Entry.entry_date <= date.fromisoformat(jalali_to_gregorian_iso(end)))
    except ValueError as exc:
        flash(str(exc), "error")
    entries = query.order_by(Entry.entry_date.asc(), Entry.id.asc()).all()
    debit = sum(int(getattr(e, "amount", 0) or 0) for e in entries if getattr(e, "entry_type", "") == "expense")
    credit = sum(int(getattr(e, "amount", 0) or 0) for e in entries if getattr(e, "entry_type", "") == "income")
    return render_template("admin/report.html", entries=entries, debit=debit, credit=credit,
                           start=start, end=end, format_amount=format_amount,
                           gregorian_to_jalali=gregorian_to_jalali)


@admin_bp.get("/logs")
@admin_required
def logs():
    AuditLog = _model("AuditLog")
    query = AuditLog.query
    if request.args.get("event"): query = query.filter_by(event_type=request.args["event"])
    if request.args.get("user_id"): query = query.filter_by(actor_user_id=request.args["user_id"])
    try:
        if request.args.get("start"):
            start_date = date.fromisoformat(jalali_to_gregorian_iso(request.args["start"]))
            query = query.filter(AuditLog.created_at >= datetime.combine(start_date, datetime.min.time(), timezone.utc))
        if request.args.get("end"):
            end_date = date.fromisoformat(jalali_to_gregorian_iso(request.args["end"]))
            query = query.filter(AuditLog.created_at <= datetime.combine(end_date, datetime.max.time(), timezone.utc))
    except ValueError as exc:
        flash(str(exc), "error")
    return render_template("admin/logs.html", logs=query.order_by(AuditLog.id.desc()).limit(500).all(),
                           audit_details_fa=_audit_details_fa, related_record_fa=_related_record_fa)


@admin_bp.post("/logs/clear")
@admin_required
def clear_logs():
    AuditLog = _model("AuditLog")
    count = AuditLog.query.delete(synchronize_session=False)
    _log("logs_cleared", f"{count} لاگ پاک شد")
    db.session.commit()
    flash("لاگ‌ها پاک شدند و رویداد پاک‌سازی ثبت شد.", "success")
    return redirect(url_for("admin.logs"))


@admin_bp.route("/backup", methods=["GET", "POST"])
@admin_required
def backup():
    Setting = _model("Setting")
    setting = Setting.query.filter_by(key="backup").first()
    if setting is None:
        setting = Setting(key="backup", auto_backup_enabled=True)
        db.session.add(setting)
        db.session.commit()
    if request.method == "POST":
        preferred = request.form.get("backup_path", "").strip() or current_app.config.get("DEFAULT_BACKUP_DIR")
        if request.form.get("action") == "save-settings":
            before = {"backup_path": setting.backup_path, "auto_backup_enabled": setting.auto_backup_enabled}
            setting.backup_path = str(preferred)
            setting.auto_backup_enabled = request.form.get("auto_backup_enabled") == "on"
            after = {"backup_path": setting.backup_path, "auto_backup_enabled": setting.auto_backup_enabled}
            _log("backup_settings_changed", "تنظیمات بکاپ تغییر کرد", before=before, after=after)
            db.session.commit()
            flash("تنظیمات بکاپ ذخیره شد.", "success")
            return redirect(url_for("admin.backup"))
        try:
            result = create_backup(current_app.config["SQLALCHEMY_DATABASE_URI"], preferred,
                                   current_app.config["DEFAULT_BACKUP_DIR"])
            _log("backup_fallback" if result["used_fallback"] else "backup_manual", "پشتیبان ایجاد شد", after={"path": str(result["path"])})
            db.session.commit()
            if result["used_fallback"]:
                flash(f"مسیر سفارشی در دسترس نبود؛ بکاپ در مسیر پیش‌فرض ذخیره شد: {result['path']}", "error")
            else:
                flash(f"پشتیبان ایجاد شد: {result['path']}", "success")
        except Exception as exc:
            _log("backup_failed", str(exc), success=False); db.session.commit(); flash(str(exc), "error")
        return redirect(url_for("admin.backup"))
    return render_template("admin/backup.html", default_path=current_app.config.get("DEFAULT_BACKUP_DIR"),
                           setting=setting)
