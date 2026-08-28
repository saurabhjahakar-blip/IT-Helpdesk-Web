from backend.db.models import Role


def _login(test_client, email, password):
    return test_client.post("/login", data={"email": email, "password": password}, follow_redirects=False)


def test_post_without_csrf_header_is_rejected(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="password123")
    _login(client, "user@example.com", "password123")

    response = client.post("/api/assets/snapshot")
    assert response.status_code == 403


def test_post_with_wrong_csrf_header_is_rejected(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="password123")
    _login(client, "user@example.com", "password123")

    response = client.post("/api/assets/snapshot", headers={"X-CSRF-Token": "not-the-real-token"})
    assert response.status_code == 403


def test_post_with_matching_csrf_header_succeeds(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="password123")
    _login(client, "user@example.com", "password123")

    token = client.cookies.get("csrf_token")
    assert token

    response = client.post("/api/assets/snapshot", headers={"X-CSRF-Token": token})
    assert response.status_code == 200


def test_logout_without_matching_form_field_is_rejected(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="password123")
    _login(client, "user@example.com", "password123")

    response = client.post("/logout", data={"csrf_token": "wrong"})
    assert response.status_code == 403
    # Session must still be valid — the rejected logout should not have revoked it.
    assert client.get("/api/system/info").status_code == 200


def test_logout_with_matching_form_field_succeeds(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="password123")
    _login(client, "user@example.com", "password123")

    token = client.cookies.get("csrf_token")
    response = client.post("/logout", data={"csrf_token": token}, follow_redirects=False)
    assert response.status_code == 303
