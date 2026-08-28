from backend.db.models import Report
from backend.services.report_service import _build_sections


def test_generate_report_creates_row_owned_by_user(employee_client, db_session, employee_user):
    response = employee_client.post("/api/reports/generate")
    assert response.status_code == 200
    row = db_session.query(Report).one()
    assert row.user_id == employee_user.id


def test_list_only_shows_own_reports(client, db_session, employee_user, technician_user):
    from backend.app import app
    from backend.auth.dependencies import require_api_user, require_csrf

    app.dependency_overrides[require_csrf] = lambda: None
    app.dependency_overrides[require_api_user] = lambda: employee_user
    client.post("/api/reports/generate")
    app.dependency_overrides[require_api_user] = lambda: technician_user
    client.post("/api/reports/generate")

    app.dependency_overrides[require_api_user] = lambda: employee_user
    response = client.get("/api/reports/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1

    app.dependency_overrides.pop(require_api_user, None)
    app.dependency_overrides.pop(require_csrf, None)


def test_download_sets_content_disposition(employee_client):
    generated = employee_client.post("/api/reports/generate").json()
    response = employee_client.get(f"/api/reports/{generated['id']}/download")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "text/html" in response.headers["content-type"]


def test_download_other_users_report_is_404(client, employee_user, technician_user):
    from backend.app import app
    from backend.auth.dependencies import require_api_user, require_csrf

    app.dependency_overrides[require_csrf] = lambda: None
    app.dependency_overrides[require_api_user] = lambda: employee_user
    generated = client.post("/api/reports/generate").json()

    app.dependency_overrides[require_api_user] = lambda: technician_user
    response = client.get(f"/api/reports/{generated['id']}/download")
    assert response.status_code == 404

    app.dependency_overrides.pop(require_api_user, None)
    app.dependency_overrides.pop(require_csrf, None)


def test_download_contains_all_ten_sections_and_ticket_link(employee_client):
    generated = employee_client.post("/api/reports/generate").json()
    response = employee_client.get(f"/api/reports/{generated['id']}/download")
    body = response.text
    for heading in [
        "Report Information",
        "Device Information",
        "Issue Details",
        "Diagnostics",
        "Troubleshooting Performed",
        "Findings",
        "Root Cause",
        "Resolution",
        "Validation",
        "Final Status",
    ]:
        assert heading in body
    assert "itdesk.miniorange.com/raiseTicket" in body


_GOOD_SYSTEM = {
    "health": {"level": "good", "status": "Good", "message": "No critical issues found"},
    "network_connected": True,
    "internet_connected": True,
    "disk_percent": 40,
    "ram_percent": 50,
}


def test_build_sections_clean_system_resolves():
    sections = _build_sections(_GOOD_SYSTEM, _GOOD_SYSTEM, [])
    assert sections["final_status"] == "Resolved — No Issues Detected"
    assert "No issues detected" in sections["issue_details"][0]
    assert "No remediation" in sections["resolution"]


def test_build_sections_surfaces_failure_as_root_cause():
    audit = [
        {
            "tool_name": "ping_test",
            "category": "command",
            "success": False,
            "error_message": "Command timed out.",
            "output_preview": None,
            "created_at": "2026-08-28T10:00:00",
        }
    ]
    sections = _build_sections(_GOOD_SYSTEM, _GOOD_SYSTEM, audit)
    assert "ping_test" in sections["root_cause"]
    assert "Command timed out." in sections["root_cause"]
    assert any("ping_test" in f for f in sections["findings"])


def test_build_sections_recommends_escalation_when_still_critical():
    bad_system = {
        **_GOOD_SYSTEM,
        "health": {"level": "critical", "status": "Critical", "message": "Disk critically full"},
        "disk_percent": 95,
    }
    sections = _build_sections(bad_system, bad_system, [])
    assert sections["final_status"] == "Unresolved — Escalation Recommended"


def test_build_sections_validation_notes_resolved_when_live_is_good():
    bad_system = {
        **_GOOD_SYSTEM,
        "health": {"level": "warning", "status": "Warning", "message": "Disk usage high"},
    }
    sections = _build_sections(bad_system, _GOOD_SYSTEM, [])
    assert any("resolved" in line.lower() for line in sections["validation"])
