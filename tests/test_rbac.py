from backend.services import windows_tools


def test_employee_tool_list_includes_everything(employee_client):
    # 2026-08-28: all tools are open to every authenticated user. device_manager/
    # services rely on Windows UAC + AD admin-group policy to block real changes;
    # cmd is open too as an explicit user decision despite not being gated by UAC.
    response = employee_client.get("/api/system/tools")
    assert response.status_code == 200
    data = response.json()
    assert "cmd" in data["launch"]
    assert "device_manager" in data["launch"]
    assert "services" in data["launch"]
    assert "task_manager" in data["launch"]
    assert "restart" in data["power"]
    assert "shutdown" in data["power"]


def test_technician_tool_list_shows_everything(technician_client):
    response = technician_client.get("/api/system/tools")
    data = response.json()
    assert "cmd" in data["launch"]
    assert "restart" in data["power"]


def test_employee_allowed_formerly_technician_only_tool(employee_client, monkeypatch):
    monkeypatch.setitem(windows_tools.LAUNCH_TOOLS, "cmd", lambda: None)
    response = employee_client.post("/api/system/tools/cmd")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_employee_allowed_employee_tool(employee_client, monkeypatch):
    monkeypatch.setitem(windows_tools.LAUNCH_TOOLS, "task_manager", lambda: None)
    response = employee_client.post("/api/system/tools/task_manager")
    assert response.status_code == 200
