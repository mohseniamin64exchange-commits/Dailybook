from datetime import date, datetime, timezone

from app.extensions import db
from app.models import AuditLog, DailyEntry, User

from .conftest import add_user, login


def test_admin_can_create_user_and_manage_users(logged_in_admin, app):
    response = logged_in_admin.post(
        "/admin/users",
        data={
            "first_name": "کاربر",
            "last_name": "جدید",
            "username": "new-user",
            "password": "new-password",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302

    with app.app_context():
        user = User.query.filter_by(username="new-user").one()
        user_id = user.id
        assert user.role == "user"
        assert user.check_password("new-password")
        assert AuditLog.query.filter_by(event_type="user_created").count() == 1

    response = logged_in_admin.post(
        f"/admin/users/{user_id}/deactivate", follow_redirects=False
    )
    assert response.status_code == 302
    response = logged_in_admin.post(
        f"/admin/users/{user_id}/activate", follow_redirects=False
    )
    assert response.status_code == 302

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.status == "active"


def test_regular_user_is_denied_all_admin_pages(client, app, regular_user):
    assert login(client, username="user").status_code == 302

    for path in ("/admin/", "/admin/users", "/admin/report", "/admin/logs", "/admin/backup"):
        response = client.get(path, follow_redirects=False)
        assert response.status_code == 302
        assert response.headers["Location"].endswith("/entries/")


def test_admin_can_reset_password_and_unlock_user(logged_in_admin, app):
    user_id = add_user(app, username="locked-user", password="old-password")
    with app.app_context():
        user = db.session.get(User, user_id)
        user.is_locked = True
        user.status = "active"
        user.failed_login_count = 5
        db.session.commit()

    response = logged_in_admin.post(
        f"/admin/users/{user_id}/reset-password",
        data={"password": "reset-password"},
        follow_redirects=False,
    )
    assert response.status_code == 302

    response = logged_in_admin.post(
        f"/admin/users/{user_id}/unlock", follow_redirects=False
    )
    assert response.status_code == 302

    with app.app_context():
        user = db.session.get(User, user_id)
        assert user.check_password("reset-password")
        assert user.is_locked is False
        assert user.failed_login_count == 0
        assert user.status == "active"
        assert AuditLog.query.filter_by(event_type="user_reset_password").count() == 1
        assert AuditLog.query.filter_by(event_type="user_unlock").count() == 1


def test_report_calculates_debit_credit_and_excludes_soft_deleted(
    logged_in_admin, app, admin
):
    with app.app_context():
        db.session.add_all(
            [
                DailyEntry(
                    entry_date=date(2024, 1, 10),
                    entry_type="expense",
                    description="هزینه نمایش",
                    amount=1200,
                    created_by_user_id=admin,
                    created_by_first_name_snapshot="Test",
                    created_by_last_name_snapshot="User",
                    created_by_username_snapshot="admin",
                ),
                DailyEntry(
                    entry_date=date(2024, 1, 11),
                    entry_type="income",
                    description="درآمد نمایش",
                    amount=3400,
                    created_by_user_id=admin,
                    created_by_first_name_snapshot="Test",
                    created_by_last_name_snapshot="User",
                    created_by_username_snapshot="admin",
                ),
                DailyEntry(
                    entry_date=date(2024, 1, 12),
                    entry_type="expense",
                    description="هزینه حذف‌شده",
                    amount=9999,
                    deleted_at=datetime.now(timezone.utc),
                    created_by_user_id=admin,
                    created_by_first_name_snapshot="Test",
                    created_by_last_name_snapshot="User",
                    created_by_username_snapshot="admin",
                ),
            ]
        )
        db.session.commit()

    response = logged_in_admin.get("/admin/report?start=۱۴۰۲/۱۰/۲۰&end=۱۴۰۲/۱۰/۲۲")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "هزینه نمایش" in body
    assert "درآمد نمایش" in body
    assert "هزینه حذف‌شده" not in body
    assert "ساعت" in body
    assert "کاربر" in body
    assert "Test User" in body
    assert "۱٬۲۰۰" in body
    assert "۳٬۴۰۰" in body
    assert "۹٬۹۹۹" not in body


def test_admin_has_ordered_fixed_sidebar(logged_in_admin):
    response = logged_in_admin.get("/admin/report")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    labels = [
        "ثبت روزانه",
        "گزارش‌ها",
        "کاربران",
        "بکاپ و بازیابی",
        "لاگ فعالیت‌ها",
        "تنظیمات",
        "خروج",
    ]
    start = body.index('class="admin-sidebar"')
    positions = [body.index(label, start) for label in labels]
    assert positions == sorted(positions)
    assert "☰" not in body


def test_remote_admin_has_no_server_sidebar(logged_in_admin):
    response = logged_in_admin.get("/entries/", environ_base={"REMOTE_ADDR": "192.168.1.25"})
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'class="admin-sidebar"' not in body


def test_regular_user_dashboard_has_no_admin_sidebar(client, app, regular_user):
    assert login(client, username="user").status_code == 302
    response = client.get("/entries/")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert 'class="admin-sidebar"' not in body
    assert "۱۰ ثبت اخیر من" in body


def test_report_date_filter_uses_jalali_range(logged_in_admin, app, admin):
    with app.app_context():
        db.session.add(
            DailyEntry(
                entry_date=date(2024, 1, 10),
                entry_type="expense",
                description="در بازه",
                amount=500,
                created_by_user_id=admin,
                created_by_first_name_snapshot="Test",
                created_by_last_name_snapshot="User",
                created_by_username_snapshot="admin",
            )
        )
        db.session.add(
            DailyEntry(
                entry_date=date(2024, 2, 10),
                entry_type="expense",
                description="خارج از بازه",
                amount=700,
                created_by_user_id=admin,
                created_by_first_name_snapshot="Test",
                created_by_last_name_snapshot="User",
                created_by_username_snapshot="admin",
            )
        )
        db.session.commit()

    response = logged_in_admin.get("/admin/report?advanced_filter=on&use_date=on&start=۱۴۰۲/۱۰/۲۰&end=۱۴۰۲/۱۰/۲۰")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "در بازه" in body
    assert "خارج از بازه" not in body


def test_admin_can_clear_logs_and_records_clear_event(logged_in_admin, app, admin):
    with app.app_context():
        db.session.add(
            AuditLog(
                event_type="test_event",
                actor_user_id=admin,
                actor_username_snapshot="admin",
                success=True,
                message="برای پاک‌سازی",
            )
        )
        db.session.commit()

    response = logged_in_admin.post("/admin/logs/clear", data={"admin_password": "correct-password"}, follow_redirects=False)
    assert response.status_code == 302

    with app.app_context():
        logs = AuditLog.query.all()
        assert len(logs) == 1
        assert logs[0].event_type == "logs_cleared"
        assert "پاک شد" in logs[0].message


def test_admin_can_create_manual_backup(logged_in_admin, app):
    backup_dir = app.config["DEFAULT_BACKUP_DIR"]
    response = logged_in_admin.post(
        "/admin/backup",
        data={"backup_path": str(backup_dir)},
        follow_redirects=False,
    )
    assert response.status_code == 302

    backups = [path for path in backup_dir.glob("*.db") if not path.name.startswith("dailybook_auto_")]
    assert len(backups) == 1
    assert backups[0].stat().st_size > 0

    with app.app_context():
        assert AuditLog.query.filter_by(event_type="backup_manual").count() == 1
