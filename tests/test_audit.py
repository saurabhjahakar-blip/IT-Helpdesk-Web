from backend.db.models import AuditLog
from backend.services.audit_service import record_tool_invocation


def test_record_tool_invocation_writes_row(db_session, employee_user):
    record_tool_invocation(
        db_session,
        employee_user,
        tool_name="ping_test",
        category="command",
        success=True,
        exit_code=0,
        output="reply from host",
        error_message=None,
        duration_ms=42,
        ip_address="127.0.0.1",
    )
    row = db_session.query(AuditLog).one()
    assert row.tool_name == "ping_test"
    assert row.success is True
    assert row.duration_ms == 42
    assert row.username_snapshot == employee_user.email


def test_record_tool_invocation_truncates_long_output(db_session, employee_user):
    record_tool_invocation(
        db_session,
        employee_user,
        tool_name="system_logs",
        category="command",
        success=True,
        exit_code=0,
        output="x" * 10_000,
        error_message=None,
        duration_ms=10,
        ip_address=None,
    )
    row = db_session.query(AuditLog).one()
    assert len(row.output_excerpt) == 4000


def test_record_tool_invocation_survives_db_failure(db_session, employee_user, monkeypatch):
    def _boom():
        raise RuntimeError("db is down")

    monkeypatch.setattr(db_session, "commit", _boom)

    # Must not raise, even though the DB write fails — the file log line is
    # the durable fallback.
    record_tool_invocation(
        db_session,
        employee_user,
        tool_name="ping_test",
        category="command",
        success=True,
        exit_code=0,
        output="ok",
        error_message=None,
        duration_ms=5,
        ip_address=None,
    )
