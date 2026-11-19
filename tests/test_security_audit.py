import pytest

from app.security_audit import (
    init_audit_db,
    record_security_event,
    read_security_events,
)


def test_audit_db_created(tmp_path):
    db = tmp_path / "security.db"
    init_audit_db(db)
    assert db.exists()


def test_record_and_read_event(tmp_path):
    db = tmp_path / "security.db"
    init_audit_db(db)

    assert record_security_event(
        db, "admin_login_success", True
    )

    events = read_security_events(db)

    assert len(events) == 1
    assert events[0]["tipo"] == "admin_login_success"
    assert events[0]["sucesso"] is True


def test_events_ordered_newest_first(tmp_path):
    db = tmp_path / "security.db"
    init_audit_db(db)

    record_security_event(db, "admin_login_failure", False)
    record_security_event(db, "admin_login_success", True)

    events = read_security_events(db)

    assert events[0]["tipo"] == "admin_login_success"
    assert events[1]["tipo"] == "admin_login_failure"


def test_invalid_event_rejected(tmp_path):
    db = tmp_path / "security.db"
    init_audit_db(db)

    with pytest.raises(ValueError):
        record_security_event(db, "unknown_event", True)


def test_invalid_success_rejected(tmp_path):
    db = tmp_path / "security.db"
    init_audit_db(db)

    with pytest.raises(ValueError):
        record_security_event(
            db, "admin_login_success", "true"
        )


def test_limit_applied(tmp_path):
    db = tmp_path / "security.db"
    init_audit_db(db)

    for _ in range(5):
        record_security_event(
            db, "admin_access_denied", False
        )

    assert len(read_security_events(db, limit=2)) == 2


def test_database_initialization_is_idempotent(tmp_path):
    db = tmp_path / "security.db"

    init_audit_db(db)
    record_security_event(db, "person_created", True)
    init_audit_db(db)

    assert len(read_security_events(db)) == 1
