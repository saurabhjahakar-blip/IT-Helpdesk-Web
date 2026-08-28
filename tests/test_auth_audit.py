from backend.db.models import AuditLog, Role


def test_login_events_write_audit_rows(client, db_session, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="password123")

    client.post("/login", data={"email": "user@example.com", "password": "wrong"})
    client.post("/login", data={"email": "user@example.com", "password": "password123"})

    events = db_session.query(AuditLog).filter(AuditLog.category == "auth").order_by(AuditLog.id).all()
    assert [e.tool_name for e in events] == ["login_failure", "login_success"]
    assert events[0].success is False
    assert events[1].success is True
    assert events[1].username_snapshot == "user@example.com"


def test_logout_is_audited(client, db_session, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="password123")
    client.post("/login", data={"email": "user@example.com", "password": "password123"})
    token = client.cookies.get("csrf_token")
    client.post("/logout", data={"csrf_token": token})

    events = db_session.query(AuditLog).filter(AuditLog.tool_name == "logout").all()
    assert len(events) == 1
    assert events[0].success is True
