import os
from datetime import timedelta
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent


def default_data_dir() -> Path:
    override = os.environ.get("DAILYBOOK_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if os.name == "nt":
        return Path(os.environ.get("PROGRAMDATA", r"C:\ProgramData")) / "DailyBook"
    return BASE_DIR / "instance"


DATA_DIR = default_data_dir()


class Config:
    DATA_DIR = DATA_DIR
    SECRET_KEY = os.environ.get("DAILYBOOK_SECRET_KEY")
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DAILYBOOK_DATABASE_URI",
        f"sqlite:///{(DATA_DIR / 'dailybook.db').as_posix()}",
    )
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"connect_args": {"timeout": 30}}
    WTF_CSRF_TIME_LIMIT = None
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = os.environ.get("DAILYBOOK_HTTPS", "0") == "1"
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)
    SESSION_REFRESH_EACH_REQUEST = True
    MAX_CONTENT_LENGTH = 2 * 1024 * 1024
    RECENT_ENTRY_LIMIT = 10
    DEFAULT_PORT = 4000
    DEFAULT_BACKUP_DIR = DATA_DIR / "backups"


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    SQLALCHEMY_ENGINE_OPTIONS = {}
    SECRET_KEY = "test-key"
