"""Audit event persistence service."""

from flask import request, has_request_context

from ..extensions import db
from ..models import AuditLog, utc_now


def record_event(
    event_type,
    *,
    actor=None,
    related_record_type=None,
    related_record_id=None,
    before=None,
    after=None,
    success=True,
    message=None,
    client_ip=None,
    commit=True,
):
    """Create an audit event for both successful and failed operations.

    ``before`` and ``after`` accept dictionaries/lists or already encoded
    JSON strings. The actor's display identity is copied immediately so the
    event remains meaningful after a user is renamed or soft-deleted.
    """
    if actor is not None:
        actor_name = " ".join(
            part for part in (actor.first_name, actor.last_name) if part
        ) or None
        actor_user_id = actor.id
        actor_username = actor.username
    else:
        actor_name = None
        actor_user_id = None
        actor_username = None

    if client_ip is None and has_request_context():
        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
        if client_ip and "," in client_ip:
            client_ip = client_ip.split(",", 1)[0].strip()

    event = AuditLog(
        event_type=event_type,
        actor_user_id=actor_user_id,
        actor_name_snapshot=actor_name,
        actor_username_snapshot=actor_username,
        related_record_type=related_record_type,
        related_record_id=related_record_id,
        before_data=AuditLog.encode_data(before),
        after_data=AuditLog.encode_data(after),
        success=bool(success),
        message=message,
        client_ip=client_ip,
        created_at=utc_now(),
    )
    db.session.add(event)
    if commit:
        db.session.commit()
    return event


def record_success(event_type, **kwargs):
    kwargs["success"] = True
    return record_event(event_type, **kwargs)


def record_failure(event_type, *, message=None, **kwargs):
    kwargs["success"] = False
    kwargs["message"] = message
    return record_event(event_type, **kwargs)
