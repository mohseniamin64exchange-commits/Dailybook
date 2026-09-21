"""Acceptance tests for the administrator-configurable server port.

These tests intentionally describe the settings contract before its
implementation exists.  The application must expose an admin-only settings
endpoint at ``/admin/settings`` with a ``server_port`` field and a resolver
``app.services.settings.resolve_server_port``.  The resolver must read the
persisted value on every application start (not only from the current process
configuration).
"""

import importlib

import pytest

from app.extensions import db
from app.models import Setting


SETTINGS_URL = "/admin/settings"


def _save_port(client, port):
    return client.post(
        SETTINGS_URL,
        data={"server_port": str(port)},
        follow_redirects=False,
    )


def _resolve_port(app):
    """Load the resolver dynamically so this file remains an acceptance test."""
    settings_module = importlib.import_module("app.services.settings")
    resolver = getattr(settings_module, "resolve_server_port")
    return resolver(app)


def test_regular_user_cannot_change_server_port(app, client, regular_user):
    from tests.conftest import login

    response = login(client, username="user")
    assert response.status_code == 302

    response = _save_port(client, 4000)

    assert response.status_code in (302, 403)
    with app.app_context():
        setting = Setting.query.filter_by(key="server_port").one_or_none()
        assert setting is None or setting.value != "4000"


@pytest.mark.parametrize("invalid_port", ["", "abc", "-1", "0", "65536", "1.5"])
def test_admin_cannot_save_invalid_server_port(app, logged_in_admin, invalid_port):
    response = _save_port(logged_in_admin, invalid_port)

    assert response.status_code in (302, 400)
    with app.app_context():
        setting = Setting.query.filter_by(key="server_port").one_or_none()
        assert setting is None or setting.value not in {"", "abc", "-1", "0", "65536", "1.5"}


def test_admin_can_save_port_4000(app, logged_in_admin):
    response = _save_port(logged_in_admin, 4000)

    assert response.status_code in (302, 200)
    with app.app_context():
        setting = Setting.query.filter_by(key="server_port").one()
        assert setting.value == "4000"


def test_admin_can_save_a_new_valid_port(app, logged_in_admin):
    response = _save_port(logged_in_admin, 4789)

    assert response.status_code in (302, 200)
    with app.app_context():
        setting = Setting.query.filter_by(key="server_port").one()
        assert setting.value == "4789"


def test_port_resolver_reads_saved_value_after_restart(app, logged_in_admin):
    assert _save_port(logged_in_admin, 4000).status_code in (302, 200)

    with app.app_context():
        database_uri = app.config["SQLALCHEMY_DATABASE_URI"]
        backup_dir = app.config["DEFAULT_BACKUP_DIR"]

    # A second app object models a process restart while retaining the same DB.
    class RestartConfig:
        TESTING = True
        SECRET_KEY = "pytest-secret-restart"
        WTF_CSRF_ENABLED = False
        SQLALCHEMY_TRACK_MODIFICATIONS = False
        SQLALCHEMY_DATABASE_URI = database_uri
        DEFAULT_BACKUP_DIR = backup_dir

    from app import create_app

    restarted_app = create_app(RestartConfig)
    with restarted_app.app_context():
        assert _resolve_port(restarted_app) == 4000


def test_settings_page_has_windows_autostart_toggle(logged_in_admin):
    response = logged_in_admin.get(SETTINGS_URL)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "windows_autostart_enabled" in body
    assert "اجرای خودکار با روشن شدن ویندوز" in body


def test_admin_can_disable_windows_autostart(app, logged_in_admin):
    response = logged_in_admin.post(
        SETTINGS_URL, data={"server_port": "4000"}, follow_redirects=False
    )
    assert response.status_code in (302, 200)
    with app.app_context():
        setting = Setting.query.filter_by(key="windows_autostart_enabled").one()
        assert setting.value == "0"


def test_admin_can_enable_windows_autostart(app, logged_in_admin):
    response = logged_in_admin.post(
        SETTINGS_URL,
        data={"server_port": "4000", "windows_autostart_enabled": "on"},
        follow_redirects=False,
    )
    assert response.status_code in (302, 200)
    with app.app_context():
        setting = Setting.query.filter_by(key="windows_autostart_enabled").one()
        assert setting.value == "1"
