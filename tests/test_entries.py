from datetime import date

from app.extensions import db
from app.models import AuditLog, DailyEntry

from .conftest import login


ENTRY = {"entry_date": "1403/01/15", "entry_type": "expense",
         "description": "خرید آزمایشی", "amount": "۱۲۳٬۴۵۶"}


def test_create_update_delete_entry_and_audit(logged_in_admin, app):
    response = logged_in_admin.post("/entries/", data=ENTRY)
    assert response.status_code == 302
    with app.app_context():
        entry = DailyEntry.query.one()
        entry_id = entry.id
        assert entry.amount == 123456
        assert entry.entry_date == date(2024, 4, 3)
        assert AuditLog.query.filter_by(event_type="create_entry").count() == 1

    response = logged_in_admin.post(f"/entries/{entry_id}/edit", data={
        **ENTRY, "entry_type": "income", "description": "ویرایش", "amount": "2000"
    })
    assert response.status_code == 302
    with app.app_context():
        entry = db.session.get(DailyEntry, entry_id)
        assert entry.description == "ویرایش"
        assert entry.entry_type == "income"
        assert AuditLog.query.filter_by(event_type="update_entry").count() == 1

    response = logged_in_admin.post(f"/entries/{entry_id}/delete")
    assert response.status_code == 302
    with app.app_context():
        entry = db.session.get(DailyEntry, entry_id)
        assert entry.deleted_at is not None
        assert AuditLog.query.filter_by(event_type="soft_delete_entry").count() == 1


def test_user_cannot_read_or_mutate_another_users_entry(client, app, admin, regular_user):
    with app.app_context():
        entry = DailyEntry(entry_date=date(2024, 1, 1), entry_type="expense", description="private",
                           amount=100, created_by_user_id=admin,
                           created_by_first_name_snapshot="Test", created_by_last_name_snapshot="User",
                           created_by_username_snapshot="admin")
        db.session.add(entry)
        db.session.commit()
        entry_id = entry.id

    assert login(client, username="user").status_code == 302
    assert client.get(f"/entries/{entry_id}/edit").status_code == 404
    assert client.post(f"/entries/{entry_id}/delete").status_code == 404
    assert client.get("/entries/").status_code == 200


def test_entries_require_login(client):
    response = client.get("/entries/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
