from fastapi.testclient import TestClient

from backend.app import app
from backend.db.models import Role


def _login(test_client, email, password):
    return test_client.post("/login", data={"email": email, "password": password}, follow_redirects=False)


def _csrf_headers(test_client):
    return {"X-CSRF-Token": test_client.cookies.get("csrf_token", "")}


def test_wrong_current_password_rejected(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="original-pass1")
    _login(client, "user@example.com", "original-pass1")
    response = client.post(
        "/api/account/change-password",
        json={"current_password": "wrong", "new_password": "new-password1", "confirm_password": "new-password1"},
        headers=_csrf_headers(client),
    )
    assert response.status_code == 400


def test_mismatched_confirmation_rejected(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="original-pass1")
    _login(client, "user@example.com", "original-pass1")
    response = client.post(
        "/api/account/change-password",
        json={
            "current_password": "original-pass1",
            "new_password": "new-password1",
            "confirm_password": "different1",
        },
        headers=_csrf_headers(client),
    )
    assert response.status_code == 400


def test_too_short_new_password_rejected(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="original-pass1")
    _login(client, "user@example.com", "original-pass1")
    response = client.post(
        "/api/account/change-password",
        json={"current_password": "original-pass1", "new_password": "short", "confirm_password": "short"},
        headers=_csrf_headers(client),
    )
    assert response.status_code == 422


def test_password_change_revokes_other_sessions_but_keeps_current(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="original-pass1")

    # A second, separate logged-in session for the same account/db.
    second_client = TestClient(app)
    _login(second_client, "user@example.com", "original-pass1")
    assert second_client.get("/api/system/info").status_code == 200

    _login(client, "user@example.com", "original-pass1")
    response = client.post(
        "/api/account/change-password",
        json={
            "current_password": "original-pass1",
            "new_password": "new-password1",
            "confirm_password": "new-password1",
        },
        headers=_csrf_headers(client),
    )
    assert response.status_code == 200

    # Current session survives...
    assert client.get("/api/system/info").status_code == 200
    # ...but the other session is revoked.
    assert second_client.get("/api/system/info").status_code == 401
