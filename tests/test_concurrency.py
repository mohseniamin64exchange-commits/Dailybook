from concurrent.futures import ThreadPoolExecutor
from datetime import date
from pathlib import Path

from app import create_app
from app.extensions import db
from app.models import DailyEntry, User


def test_five_concurrent_entries_on_file_sqlite(tmp_path):
    database_path = Path(tmp_path) / "concurrency.db"

    class FileSQLiteConfig:
        TESTING = True
        SECRET_KEY = "concurrency-test-key"
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{database_path}"
        SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}
        DEFAULT_BACKUP_DIR = Path(tmp_path) / "backups"

    application = create_app(FileSQLiteConfig)
    with application.app_context():
        user = User(
            first_name="Concurrent",
            last_name="Tester",
            username="concurrent-user",
            password_hash="unused",
            role="user",
            status="active",
            failed_login_count=0,
            is_locked=False,
        )
        db.session.add(user)
        db.session.commit()
        user_id = user.id

    def create_entry(index):
        with application.app_context():
            try:
                entry = DailyEntry(
                    entry_date=date(2024, 1, 1),
                    entry_type="expense",
                    description=f"همزمانی {index}",
                    amount=index,
                    created_by_user_id=user_id,
                    created_by_first_name_snapshot="Concurrent",
                    created_by_last_name_snapshot="Tester",
                    created_by_username_snapshot="concurrent-user",
                )
                db.session.add(entry)
                db.session.commit()
                return entry.id
            finally:
                db.session.remove()

    with ThreadPoolExecutor(max_workers=5) as executor:
        entry_ids = list(executor.map(create_entry, range(1, 6)))

    with application.app_context():
        entries = DailyEntry.query.order_by(DailyEntry.id).all()
        assert len(entries) == 5
        assert len(set(entry_ids)) == 5
        assert {entry.id for entry in entries} == set(entry_ids)
        assert {entry.amount for entry in entries} == {1, 2, 3, 4, 5}
