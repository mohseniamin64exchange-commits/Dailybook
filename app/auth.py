"""Authentication and first-admin flows for DailyBook.

The module deliberately only depends on the conventional ``User`` and
``AuditLog`` model APIs.  It therefore remains usable while the rest of the
application is being built.
"""

from datetime import datetime, timezone
from pathlib import Path
from functools import wraps

from flask import Blueprint, abort, current_app, flash, redirect, render_template, request, session, url_for
from urllib.parse import urlsplit
from flask_login import current_user, login_required, login_user, logout_user
from flask_wtf import FlaskForm
from werkzeug.security import check_password_hash, generate_password_hash
from wtforms import PasswordField, StringField, SubmitField
from wtforms.validators import DataRequired, Length, EqualTo

from .extensions import db


auth_bp = Blueprint("auth", __name__, url_prefix="/auth")
MAX_FAILED_LOGINS = 5
ADMIN_RECOVERY_FILE = "admin-password-recovery.ready"


class AdminSetupForm(FlaskForm):
    first_name = StringField("نام", validators=[DataRequired(), Length(max=120)])
    last_name = StringField("نام خانوادگی", validators=[DataRequired(), Length(max=120)])
    username = StringField("نام کاربری", validators=[DataRequired(), Length(min=3, max=80)])
    password = PasswordField("رمز عبور", validators=[DataRequired(), Length(min=8, max=128)])
    confirm_password = PasswordField(
        "تکرار رمز عبور",
        validators=[DataRequired(), EqualTo("password", message="تکرار رمز عبور یکسان نیست.")],
    )
    submit = SubmitField("ساخت ادمین اصلی")


class LoginForm(FlaskForm):
    username = StringField("نام کاربری", validators=[DataRequired(), Length(max=80)])
    password = PasswordField("رمز عبور", validators=[DataRequired()])
    submit = SubmitField("ورود")


def _admin_recovery_path():
    return Path(current_app.config["DATA_DIR"]) / ADMIN_RECOVERY_FILE


def _is_local_request():
    return (request.remote_addr or "").split("%", 1)[0] in {"127.0.0.1", "::1"}


def _admin_recovery_available():
    return _is_local_request() and _admin_recovery_path().is_file()

def _models():
    from .models import AuditLog, User

    return User, AuditLog


def _columns(model):
    try:
        return {column.name for column in model.__table__.columns}
    except (AttributeError, TypeError):
        return set()


def _audit(event_type, user=None, result="success", description="", error_message=None):
    """Write an audit row using only columns available on the current model."""
    try:
        _, AuditLog = _models()
        columns = _columns(AuditLog)
        now = datetime.now(timezone.utc)
        values = {
            "event_type": event_type,
            "actor_user_id": getattr(user, "id", None),
            "user_id": getattr(user, "id", None),
            "actor_name_snapshot": " ".join(
                part for part in (getattr(user, "first_name", None), getattr(user, "last_name", None)) if part
            ) or None,
            "actor_username_snapshot": getattr(user, "username", None),
            "snapshot_first_name": getattr(user, "first_name", None),
            "snapshot_last_name": getattr(user, "last_name", None),
            "snapshot_username": getattr(user, "username", None),
            "occurred_at": now,
            "created_at": now,
            "result": result,
            "outcome": result,
            "description": description,
            "error_message": error_message,
            "client_ip": _client_ip(),
        }
        if columns:
            values = {key: value for key, value in values.items() if key in columns}
        db.session.add(AuditLog(**values))
        db.session.commit()
    except Exception:
        db.session.rollback()


def _password_matches(user, password):
    checker = getattr(user, "check_password", None)
    if callable(checker):
        return bool(checker(password))
    stored = getattr(user, "password_hash", "")
    return bool(stored) and check_password_hash(stored, password)


def _set_password(user, password):
    setter = getattr(user, "set_password", None)
    if callable(setter):
        setter(password)
    else:
        user.password_hash = generate_password_hash(password)


def _is_inactive(user):
    status = str(getattr(user, "status", "active") or "active").lower()
    return status in {"inactive", "deleted", "disabled", "deactive", "غیرفعال"}


def _is_locked(user):
    return bool(getattr(user, "is_locked", False)) or str(getattr(user, "status", "")).lower() in {"locked", "قفل"}


def _set_attr_if_present(obj, name, value):
    if hasattr(obj, name):
        setattr(obj, name, value)


def _client_ip():
    """Return the first client address seen by the local application."""
    forwarded = request.headers.get("X-Forwarded-For", "")
    return (forwarded.split(",", 1)[0].strip() or request.remote_addr)

def admin_required(view):
    @wraps(view)
    @login_required
    def wrapped(*args, **kwargs):
        if str(getattr(current_user, "role", "")).lower() not in {"admin", "administrator", "ادمین"}:
            abort(403)
        return view(*args, **kwargs)

    return wrapped


@auth_bp.route("/setup-admin", methods=["GET", "POST"])
def setup_admin():
    User, _ = _models()
    if User.query.first() is not None:
        return redirect(url_for("auth.login"))
    form = AdminSetupForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        if User.query.filter_by(username=username).first() is not None:
            form.username.errors.append("این نام کاربری قبلاً استفاده شده است.")
        else:
            user = User(
                first_name=form.first_name.data.strip(),
                last_name=form.last_name.data.strip(),
                username=username,
                role="admin",
                status="active",
                failed_login_count=0,
                is_locked=False,
            )
            _set_password(user, form.password.data)
            db.session.add(user)
            db.session.commit()
            _audit("admin_setup", user, description="ایجاد ادمین اصلی")
            login_user(user)
            session.permanent = True
            return redirect(url_for("entries.dashboard"))
    return render_template("auth/setup_admin.html", form=form)


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("entries.dashboard"))
    User, _ = _models()
    form = LoginForm()
    if form.validate_on_submit():
        username = form.username.data.strip()
        user = User.query.filter_by(username=username).first()
        if user is None:
            _audit("login_failed", description=f"نام کاربری ناشناس: {username}", result="failure", error_message="unknown_username")
            flash("نام کاربری یا رمز عبور نادرست است.", "error")
        elif _is_inactive(user):
            _audit("login_failed_inactive", user, result="failure", description="تلاش ورود کاربر غیرفعال")
            flash("این حساب غیرفعال است.", "error")
        elif _is_locked(user):
            _audit("login_failed_locked", user, result="failure", description="تلاش ورود حساب قفل‌شده")
            flash("این حساب قفل شده است. با مدیر سیستم تماس بگیرید.", "error")
        elif not _password_matches(user, form.password.data):
            count = int(getattr(user, "failed_login_count", 0) or 0) + 1
            _set_attr_if_present(user, "failed_login_count", count)
            locked = count >= MAX_FAILED_LOGINS
            if locked:
                _set_attr_if_present(user, "is_locked", True)
            db.session.commit()
            _audit("account_locked" if locked else "login_failed", user, result="failure", description=f"تلاش ناموفق شماره {count}")
            flash("حساب شما پس از پنج تلاش ناموفق قفل شد." if locked else "نام کاربری یا رمز عبور نادرست است.", "error")
        else:
            _set_attr_if_present(user, "failed_login_count", 0)
            db.session.commit()
            login_user(user)
            session.permanent = True
            _audit("login_success", user, description="ورود موفق")
            next_url = request.args.get("next", "")
            if not next_url or urlsplit(next_url).netloc:
                next_url = url_for("entries.dashboard")
            return redirect(next_url)
    return render_template("auth/login.html", form=form, recovery_available=_admin_recovery_available())


@auth_bp.route("/recover-admin", methods=["GET", "POST"])
def recover_admin():
    if not _admin_recovery_available():
        abort(404)
    User, _ = _models()
    admins = User.query.filter(User.role.in_(["admin", "administrator", "ادمین"])).all()
    if len(admins) != 1:
        flash("بازیابی فقط برای یک ادمین اصلی فعال است.", "error")
        return redirect(url_for("auth.login"))
    if request.method == "POST":
        password = str(request.form.get("password") or "")
        confirmation = str(request.form.get("confirm_password") or "")
        if len(password) < 8:
            flash("رمز عبور باید حداقل ۸ نویسه باشد.", "error")
        elif password != confirmation:
            flash("تکرار رمز عبور یکسان نیست.", "error")
        else:
            user = admins[0]
            _set_password(user, password)
            _set_attr_if_present(user, "failed_login_count", 0)
            _set_attr_if_present(user, "is_locked", False)
            if str(getattr(user, "status", "")).lower() in {"locked", "قفل"}:
                _set_attr_if_present(user, "status", "active")
            db.session.commit()
            _audit("admin_password_recovered", user, description="بازیابی رمز ادمین اصلی با فرمان محلی")
            try:
                _admin_recovery_path().unlink()
            except OSError:
                pass
            flash("رمز ادمین اصلی با موفقیت تغییر کرد. اکنون وارد شوید.", "success")
            return redirect(url_for("auth.login"))
    return render_template("auth/recover_admin.html")

@auth_bp.post("/logout")
@login_required
def logout():
    user = current_user._get_current_object()
    _audit("logout", user, description="خروج از حساب")
    logout_user()
    flash("با موفقیت خارج شدید.", "success")
    return redirect(url_for("auth.login"))
