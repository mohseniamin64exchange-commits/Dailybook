"""Arm the one-time local admin password recovery page."""
from pathlib import Path
import sys

sys.stdout.reconfigure(encoding="utf-8")

from app import create_app
from config import Config
from app.models import User


class RecoveryConfig(Config):
    TESTING = True


def main():
    app = create_app(RecoveryConfig)
    marker = Path(app.config["DATA_DIR"]) / "admin-password-recovery.ready"
    with app.app_context():
        admins = User.query.filter(User.role.in_(["admin", "administrator", "ادمین"])).all()
        if len(admins) != 1:
            print("بازیابی فقط زمانی فعال می‌شود که دقیقاً یک ادمین اصلی وجود داشته باشد.")
            return 1
        if marker.exists():
            print("بازیابی رمز قبلاً فعال شده است؛ صفحه ورود را روی همین سیستم باز کنید.")
            return 0
        marker.write_text("one-time-local-recovery", encoding="utf-8")
        print("بازیابی یک‌بارمصرف فعال شد. صفحه ورود را روی همین سیستم باز کنید.")
        print("پس از ثبت رمز جدید، این دسترسی خودکار مصرف و غیرفعال می‌شود.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())