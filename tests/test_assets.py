from backend.db.models import AssetSnapshot


def test_capture_snapshot_creates_row(employee_client, db_session, employee_user):
    response = employee_client.post("/api/assets/snapshot")
    assert response.status_code == 200
    row = db_session.query(AssetSnapshot).one()
    assert row.captured_by_user_id == employee_user.id
    assert row.computer_name


def test_list_returns_newest_first(employee_client, db_session):
    employee_client.post("/api/assets/snapshot")
    employee_client.post("/api/assets/snapshot")
    response = employee_client.get("/api/assets/")
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 2
    assert data[0]["id"] > data[1]["id"]
