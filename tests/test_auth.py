from app.extensions import db
from app.models import AuditLog, User

from .conftest import login


def test_setup_admin_creates_admin_and_audit(client, app):
    response = client.post("/auth/setup-admin", data={
        "first_name": "مدیر", "last_name": "آزمایشی", "username": "firstadmin",
        "password": "strong-password", "confirm_password": "strong-password",
    })

    assert response.status_code == 302
    with app.app_context():
        user = User.query.filter_by(username="firstadmin").one()
        assert user.role == "admin"
        assert user.check_password("strong-password")
        assert AuditLog.query.filter_by(event_type="admin_setup").count() == 1


def test_setup_is_unavailable_after_first_user(client, app, admin):
    response = client.get("/auth/setup-admin")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_login_success_and_audit(client, app, admin):
    response = login(client)
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/entries/")
    with app.app_context():
        assert AuditLog.query.filter_by(event_type="login_success").count() == 1


def test_five_failed_logins_lock_account(client, app, admin):
    for _ in range(5):
        response = login(client, password="wrong-password")
        assert response.status_code == 200
    with app.app_context():
        user = db.session.get(User, admin)
        assert user.is_locked is True
        assert user.status == "active"
        assert AuditLog.query.filter_by(event_type="account_locked").count() == 1

    response = login(client)
    assert response.status_code == 200
    with app.app_context():
        assert AuditLog.query.filter_by(event_type="login_failed_locked").count() == 1


def test_inactive_user_cannot_login(client, app):
    from .conftest import add_user
    add_user(app, username="inactive", status="inactive")
    response = login(client, username="inactive")
    assert response.status_code == 200
    with app.app_context():
        assert AuditLog.query.filter_by(event_type="login_failed_inactive").count() == 1
