"""Routes for the authenticated user's income and expense entries."""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from .extensions import db
from .utils import format_amount, gregorian_to_jalali, jalali_to_gregorian_iso, parse_amount


entries_bp = Blueprint("entries", __name__, url_prefix="/entries")


def _models():
    from .models import AuditLog, DailyEntry
    return DailyEntry, AuditLog


def _owner_filter(query, model):
    return query.filter(model.created_by_user_id == current_user.id, model.deleted_at.is_(None))


def _snapshot(entry):
    return {"id": entry.id, "entry_date": str(entry.entry_date), "entry_type": entry.entry_type,
            "description": entry.description, "amount": str(entry.amount),
            "created_by_user_id": entry.created_by_user_id}


def _audit(AuditLog, event_type, record_id, before, after, message=""):
    actor_name = " ".join(filter(None, [getattr(current_user, "first_name", ""), getattr(current_user, "last_name", "")])).strip()
    db.session.add(AuditLog(event_type=event_type, actor_user_id=current_user.id,
        actor_name_snapshot=actor_name, actor_username_snapshot=current_user.username,
        related_record_type="DailyEntry", related_record_id=record_id,
        before_data=json.dumps(before, ensure_ascii=False), after_data=json.dumps(after, ensure_ascii=False),
        success=True, message=message, client_ip=request.remote_addr,
        created_at=datetime.now(timezone.utc)))


def _form_data():
    entry_type = request.form.get("entry_type", "").strip()
    if entry_type not in {"expense", "income"}:
        raise ValueError("نوع ثبت باید هزینه یا درآمد باشد.")
    description = request.form.get("description", "").strip()
    if not description or len(description) > 500:
        raise ValueError("شرح ثبت الزامی و حداکثر ۵۰۰ نویسه است.")
    entry_date = date.fromisoformat(jalali_to_gregorian_iso(request.form.get("entry_date", "")))
    return entry_type, description, parse_amount(request.form.get("amount", "")), entry_date


@entries_bp.route("/", methods=["GET", "POST"])
@login_required
def dashboard():
    DailyEntry, AuditLog = _models()
    if request.method == "POST":
        try:
            entry_type, description, amount, entry_date = _form_data()
            entry = DailyEntry(entry_date=entry_date, entry_type=entry_type, description=description,
                amount=amount, created_by_user_id=current_user.id,
                created_by_first_name_snapshot=getattr(current_user, "first_name", ""),
                created_by_last_name_snapshot=getattr(current_user, "last_name", ""),
                created_by_username_snapshot=current_user.username, created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc))
            db.session.add(entry)
            db.session.flush()
            _audit(AuditLog, "create_entry", entry.id, {}, _snapshot(entry))
            db.session.commit()
            flash("ثبت با موفقیت ذخیره شد.", "success")
            return redirect(url_for("entries.dashboard", saved=1))
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc), "error")
    entries = _owner_filter(DailyEntry.query, DailyEntry).order_by(DailyEntry.entry_date.desc(), DailyEntry.id.desc()).limit(10).all()
    return render_template("entries/dashboard.html", entries=entries, gregorian_to_jalali=gregorian_to_jalali,
                           format_amount=format_amount, edit_entry=None,
                           today_jalali=gregorian_to_jalali(date.today()))


@entries_bp.route("/<int:entry_id>/edit", methods=["GET", "POST"])
@login_required
def edit(entry_id):
    DailyEntry, AuditLog = _models()
    entry = _owner_filter(DailyEntry.query, DailyEntry).filter_by(id=entry_id).first_or_404()
    if request.method == "POST":
        try:
            before = _snapshot(entry)
            entry.entry_type, entry.description, entry.amount, entry.entry_date = _form_data()
            entry.updated_at = datetime.now(timezone.utc)
            db.session.flush()
            _audit(AuditLog, "update_entry", entry.id, before, _snapshot(entry))
            after = _snapshot(entry)
            for field, event in {
                "entry_date": "entry_date_changed",
                "entry_type": "entry_type_changed",
                "description": "entry_description_changed",
                "amount": "entry_amount_changed",
            }.items():
                if before.get(field) != after.get(field):
                    _audit(AuditLog, event, entry.id, {field: before.get(field)}, {field: after.get(field)})
            db.session.commit()
            flash("ثبت ویرایش شد.", "success")
            return redirect(url_for("entries.dashboard"))
        except (ValueError, TypeError) as exc:
            db.session.rollback()
            flash(str(exc), "error")
    entries = _owner_filter(DailyEntry.query, DailyEntry).order_by(DailyEntry.entry_date.desc(), DailyEntry.id.desc()).limit(10).all()
    return render_template("entries/dashboard.html", entries=entries, gregorian_to_jalali=gregorian_to_jalali,
                           format_amount=format_amount, edit_entry=entry)


@entries_bp.post("/<int:entry_id>/delete")
@login_required
def delete(entry_id):
    DailyEntry, AuditLog = _models()
    entry = _owner_filter(DailyEntry.query, DailyEntry).filter_by(id=entry_id).first_or_404()
    before = _snapshot(entry)
    entry.deleted_at = datetime.now(timezone.utc)
    entry.updated_at = entry.deleted_at
    _audit(AuditLog, "soft_delete_entry", entry.id, before, _snapshot(entry), "حذف نرم")
    db.session.commit()
    flash("ثبت حذف شد.", "success")
    return redirect(url_for("entries.dashboard"))
