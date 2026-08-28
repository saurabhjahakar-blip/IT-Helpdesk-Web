from backend.db.models import Report


def test_generate_report_creates_row_owned_by_user(employee_client, db_session, employee_user):
    response = employee_client.post("/api/reports/generate")
    assert response.status_code == 200
    row = db_session.query(Report).one()
    assert row.user_id == employee_user.id


def test_list_only_shows_own_reports(client, db_session, employee_user, technician_user):
    from backend.app import app
    from backend.auth.dependencies import require_api_user

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


def test_download_sets_content_disposition(employee_client):
    generated = employee_client.post("/api/reports/generate").json()
    response = employee_client.get(f"/api/reports/{generated['id']}/download")
    assert response.status_code == 200
    assert "attachment" in response.headers["content-disposition"]
    assert "text/html" in response.headers["content-type"]


def test_download_other_users_report_is_404(client, employee_user, technician_user):
    from backend.app import app
    from backend.auth.dependencies import require_api_user

    app.dependency_overrides[require_api_user] = lambda: employee_user
    generated = client.post("/api/reports/generate").json()

    app.dependency_overrides[require_api_user] = lambda: technician_user
    response = client.get(f"/api/reports/{generated['id']}/download")
    assert response.status_code == 404

    app.dependency_overrides.pop(require_api_user, None)
