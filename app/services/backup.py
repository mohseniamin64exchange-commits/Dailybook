"""Database backup helpers used by the administrator area."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta
import threading
import time
from pathlib import Path
import shutil
import sqlite3


def _sqlite_path(uri: str | None) -> Path:
    if not uri or not uri.startswith("sqlite:///"):
        raise ValueError("Backup فقط برای SQLite پشتیبانی می‌شود.")
    return Path(uri.removeprefix("sqlite:///"))


def create_backup(database_uri: str, preferred_dir: str | Path | None,
                  fallback_dir: str | Path, prefix: str = "dailybook") -> dict:
    """Create a consistent SQLite copy, falling back if the custom path fails."""
    source = _sqlite_path(database_uri).resolve()
    if not source.exists():
        raise FileNotFoundError(f"فایل دیتابیس پیدا نشد: {source}")
    from ..utils import gregorian_to_jalali, TEHRAN_TIMEZONE
    local_now = datetime.now(timezone.utc).astimezone(TEHRAN_TIMEZONE)
    jalali_date = gregorian_to_jalali(local_now.date()).replace("/", "-")
    backup_kind = "Auto" if prefix == "dailybook_auto" else "Manual"
    stamp = local_now.strftime("%H-%M-%S-%f")
    filename = f"DailyBook-Backup-v1.0.0-{backup_kind}-{jalali_date}_{stamp}.db"
    requested = Path(preferred_dir) if preferred_dir else Path(fallback_dir)
    fallback = Path(fallback_dir)
    used_fallback = False
    errors: list[str] = []
    for directory in (requested, fallback):
        if used_fallback and directory == requested:
            continue
        try:
            directory.mkdir(parents=True, exist_ok=True)
            destination = directory / filename
            with sqlite3.connect(source) as src, sqlite3.connect(destination) as dst:
                src.backup(dst)
            with sqlite3.connect(destination) as check:
                result = check.execute("PRAGMA integrity_check").fetchone()
                if not result or result[0] != "ok":
                    destination.unlink(missing_ok=True)
                    raise sqlite3.DatabaseError("اعتبارسنجی فایل پشتیبان ناموفق بود.")
            return {"path": destination, "used_fallback": used_fallback,
                    "requested_path": requested, "errors": errors}
        except (OSError, sqlite3.Error) as exc:
            errors.append(f"{directory}: {exc}")
            if directory == requested:
                used_fallback = True
    raise OSError("تهیه پشتیبان ناموفق بود: " + " | ".join(errors))


def restore_backup(backup_file: str | Path, database_uri: str) -> Path:
    """Restore a backup after validating that it is a readable SQLite database."""
    backup = Path(backup_file)
    target = _sqlite_path(database_uri)
    if not backup.exists():
        raise FileNotFoundError("فایل پشتیبان پیدا نشد.")
    with sqlite3.connect(backup) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise sqlite3.DatabaseError("فایل پشتیبان معتبر نیست.")
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
        shutil.copy2(target, target.with_name(f"{target.name}.before_restore_{stamp}"))
    temp = target.with_suffix(target.suffix + ".restore.tmp")
    shutil.copy2(backup, temp)
    temp.replace(target)
    with sqlite3.connect(target) as conn:
        result = conn.execute("PRAGMA integrity_check").fetchone()
        if not result or result[0] != "ok":
            raise sqlite3.DatabaseError("اعتبارسنجی دیتابیس بازیابی‌شده ناموفق بود.")
    return target


def _backup_time(setting_model) -> str:
    time_setting = setting_model.query.filter_by(key="backup_time").first()
    return (time_setting.value if time_setting and time_setting.value else "18:00")


def run_daily_auto_backup(app, now=None) -> dict | None:
    """Create at most one automatic backup per local day after the configured time."""
    if app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:":
        return None
    from ..extensions import db
    from ..models import Setting
    from .audit import record_event

    now = now or datetime.now().astimezone()
    today = now.date().isoformat()
    setting = Setting.query.filter_by(key="backup").first()
    if setting is None:
        setting = Setting(key="backup", auto_backup_enabled=True)
        db.session.add(setting)
        db.session.commit()
    scheduled = _backup_time(Setting)
    try:
        hh, mm = (int(part) for part in scheduled.split(":", 1))
    except (TypeError, ValueError):
        hh, mm = 18, 0
    if not setting.auto_backup_enabled or (now.hour, now.minute) < (hh, mm):
        return None
    last = setting.value or ""
    if last.startswith(today):
        return None
    try:
        result = create_backup(
            app.config["SQLALCHEMY_DATABASE_URI"],
            setting.backup_path or app.config["DEFAULT_BACKUP_DIR"],
            app.config["DEFAULT_BACKUP_DIR"],
            prefix="dailybook_auto",
        )
        setting.value = now.isoformat()
        record_event(
            "backup_auto_fallback" if result["used_fallback"] else "backup_auto",
            success=True, after={"path": str(result["path"])}, commit=False,
        )
        db.session.commit()
        return result
    except Exception as exc:
        db.session.rollback()
        record_event("backup_auto_failed", success=False, message=str(exc))
        return None


def next_backup_datetime(enabled: bool, backup_time: str, last_value: str | None = None, now=None):
    if not enabled:
        return None
    now = now or datetime.now().astimezone()
    try:
        hh, mm = (int(part) for part in backup_time.split(":", 1))
    except (TypeError, ValueError):
        hh, mm = 18, 0
    candidate = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
    if candidate <= now or (last_value or "").startswith(now.date().isoformat()):
        candidate += timedelta(days=1)
    return candidate


def start_auto_backup_scheduler(app):
    """Start one lightweight daemon that checks the configured backup time."""
    if app.extensions.get("dailybook_backup_scheduler_started"):
        return
    app.extensions["dailybook_backup_scheduler_started"] = True

    def worker():
        while True:
            try:
                with app.app_context():
                    run_daily_auto_backup(app)
            except Exception:
                app.logger.exception("Automatic backup scheduler failed")
            time.sleep(30)

    threading.Thread(target=worker, name="dailybook-auto-backup", daemon=True).start()
