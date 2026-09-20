"""Database backup helpers used by the administrator area."""
from __future__ import annotations

from datetime import datetime, timezone
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
    stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    filename = f"{prefix}_{stamp}.db"
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


def run_daily_auto_backup(app) -> dict | None:
    """Create at most one automatic backup per UTC day."""
    if app.config["SQLALCHEMY_DATABASE_URI"] == "sqlite:///:memory:":
        return None
    from ..extensions import db
    from ..models import Setting
    from .audit import record_event

    today = datetime.now(timezone.utc).date().isoformat()
    setting = Setting.query.filter_by(key="backup").first()
    if setting is None:
        setting = Setting(key="backup", auto_backup_enabled=True)
        db.session.add(setting)
        db.session.commit()
    if not setting.auto_backup_enabled or (setting.value or "").startswith(today):
        return None
    try:
        result = create_backup(
            app.config["SQLALCHEMY_DATABASE_URI"],
            setting.backup_path or app.config["DEFAULT_BACKUP_DIR"],
            app.config["DEFAULT_BACKUP_DIR"],
            prefix="dailybook_auto",
        )
        setting.value = datetime.now(timezone.utc).isoformat()
        record_event(
            "backup_auto_fallback" if result["used_fallback"] else "backup_auto",
            success=True,
            after={"path": str(result["path"])},
            commit=False,
        )
        db.session.commit()
        return result
    except Exception as exc:
        db.session.rollback()
        record_event("backup_auto_failed", success=False, message=str(exc))
        return None
