import pytest

from backend.db.models import AuditLog
from backend.services import windows_tools
from backend.services.system_service import CommandResult


@pytest.fixture(autouse=True)
def _reset_power_cooldown():
    windows_tools._last_power_at.clear()
    yield
    windows_tools._last_power_at.clear()


def test_launch_tool_command_success(db_session, employee_user, monkeypatch):
    monkeypatch.setitem(
        windows_tools.COMMAND_TOOLS,
        "dns_flush",
        lambda: CommandResult(command=["ipconfig"], returncode=0, stdout="flushed"),
    )
    result = windows_tools.launch_tool("dns_flush", user=employee_user, db=db_session)
    assert result["status"] == "ok"
    assert result["output"] == "flushed"

    row = db_session.query(AuditLog).one()
    assert row.tool_name == "dns_flush"
    assert row.success is True
    assert row.username_snapshot == employee_user.email


def test_launch_tool_command_failure_is_audited(db_session, employee_user, monkeypatch):
    monkeypatch.setitem(
        windows_tools.COMMAND_TOOLS,
        "dns_flush",
        lambda: CommandResult(command=["ipconfig"], returncode=1, stdout="", stderr="denied"),
    )
    windows_tools.launch_tool("dns_flush", user=employee_user, db=db_session)
    row = db_session.query(AuditLog).one()
    assert row.success is False
    assert row.exit_code == 1


def test_launch_tool_launch_category(db_session, employee_user, monkeypatch):
    called = {}
    monkeypatch.setitem(windows_tools.LAUNCH_TOOLS, "task_manager", lambda: called.setdefault("ran", True))
    result = windows_tools.launch_tool("task_manager", user=employee_user, db=db_session)
    assert called["ran"] is True
    assert result["status"] == "ok"
    row = db_session.query(AuditLog).one()
    assert row.success is True


def test_launch_tool_launch_failure_raises_and_audits(db_session, employee_user, monkeypatch):
    def _boom():
        raise RuntimeError("no such exe")

    monkeypatch.setitem(windows_tools.LAUNCH_TOOLS, "task_manager", _boom)
    with pytest.raises(RuntimeError):
        windows_tools.launch_tool("task_manager", user=employee_user, db=db_session)
    row = db_session.query(AuditLog).one()
    assert row.success is False
    assert "no such exe" in row.error_message


def test_employee_allowed_cmd(db_session, employee_user, monkeypatch):
    # 2026-08-28: cmd is open to everyone (explicit user decision), same as
    # every other tool — TECHNICIAN_ONLY_TOOLS is empty by default.
    monkeypatch.setitem(windows_tools.LAUNCH_TOOLS, "cmd", lambda: None)
    result = windows_tools.launch_tool("cmd", user=employee_user, db=db_session)
    assert result["status"] == "ok"


def test_technician_only_gate_still_enforced_if_populated(db_session, employee_user, monkeypatch):
    # The gate mechanism itself must still work for whatever a future tool
    # needs restricted, even though nothing uses it today.
    monkeypatch.setattr(windows_tools, "TECHNICIAN_ONLY_TOOLS", {"task_manager"})
    with pytest.raises(PermissionError):
        windows_tools.launch_tool("task_manager", user=employee_user, db=db_session)
    assert db_session.query(AuditLog).count() == 0


def test_employee_allowed_to_restart_own_machine(db_session, employee_user, monkeypatch):
    monkeypatch.setitem(
        windows_tools.POWER_TOOLS,
        "restart",
        lambda: CommandResult(command=["shutdown"], returncode=0),
    )
    result = windows_tools.launch_tool("restart", user=employee_user, db=db_session)
    assert result["status"] == "ok"


def test_technician_allowed_cmd(db_session, technician_user, monkeypatch):
    monkeypatch.setitem(windows_tools.LAUNCH_TOOLS, "cmd", lambda: None)
    result = windows_tools.launch_tool("cmd", user=technician_user, db=db_session)
    assert result["status"] == "ok"


def test_power_tool_cooldown(db_session, technician_user, monkeypatch):
    monkeypatch.setitem(
        windows_tools.POWER_TOOLS,
        "restart",
        lambda: CommandResult(command=["shutdown"], returncode=0),
    )
    windows_tools.launch_tool("restart", user=technician_user, db=db_session)
    with pytest.raises(windows_tools.ToolCooldownError):
        windows_tools.launch_tool("restart", user=technician_user, db=db_session)


def test_power_tool_failure_surfaces_real_output(db_session, technician_user, monkeypatch):
    monkeypatch.setitem(
        windows_tools.POWER_TOOLS,
        "restart",
        lambda: CommandResult(command=["shutdown"], returncode=1, stderr="Access is denied."),
    )
    result = windows_tools.launch_tool("restart", user=technician_user, db=db_session)
    assert result["status"] == "error"
    assert "Access is denied" in result["output"]


def test_ping_test_passes_host_kwarg(db_session, employee_user, monkeypatch):
    captured = {}

    def _fake_ping(host="8.8.8.8"):
        captured["host"] = host
        return CommandResult(command=["ping"], returncode=0, stdout="reply")

    monkeypatch.setitem(windows_tools.COMMAND_TOOLS, "ping_test", _fake_ping)
    windows_tools.launch_tool("ping_test", user=employee_user, db=db_session, host="1.1.1.1")
    assert captured["host"] == "1.1.1.1"


def test_unknown_tool_raises_value_error(db_session, employee_user):
    with pytest.raises(ValueError):
        windows_tools.launch_tool("does_not_exist", user=employee_user, db=db_session)
