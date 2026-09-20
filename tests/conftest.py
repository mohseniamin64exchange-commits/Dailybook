from pathlib import Path

import pytest

from app import create_app
from app.extensions import db
from app.models import AuditLog, DailyEntry, User


@pytest.fixture()
def app(tmp_path):
    class TestConfig:
        TESTING = True
        SECRET_KEY = "pytest-secret"
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SQLALCHEMY_DATABASE_URI = f"sqlite:///{tmp_path / 'test.db'}"
        DEFAULT_BACKUP_DIR = Path(tmp_path) / "backups"

    application = create_app(TestConfig)
    with application.app_context():
        db.drop_all()
        db.create_all()
    yield application
    with application.app_context():
        db.session.remove()
        db.drop_all()


@pytest.fixture()
def client(app):
    return app.test_client()


def add_user(app, username="admin", password="correct-password", role="admin", status="active"):
    with app.app_context():
        user = User(first_name="Test", last_name="User", username=username,
                    role=role, status=status, failed_login_count=0, is_locked=False)
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        return user.id


@pytest.fixture()
def admin(app):
    return add_user(app)


@pytest.fixture()
def regular_user(app):
    return add_user(app, username="user", role="user")


def login(client, username="admin", password="correct-password"):
    return client.post("/auth/login", data={"username": username, "password": password},
                       follow_redirects=False)


@pytest.fixture()
def logged_in_admin(client, admin):
    response = login(client)
    assert response.status_code == 302
    return client


@pytest.fixture()
def models():
    return User, DailyEntry, AuditLog
