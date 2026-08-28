from backend.db.models import Role


def test_unauthenticated_page_redirects_to_login(client):
    response = client.get("/", follow_redirects=False)
    assert response.status_code == 303
    assert response.headers["location"].startswith("/login")


def test_unauthenticated_api_returns_401(client):
    response = client.get("/api/system/info")
    assert response.status_code == 401


def test_login_wrong_password_returns_401(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="correct-horse-battery")
    response = client.post("/login", data={"email": "user@example.com", "password": "wrong"})
    assert response.status_code == 401
    assert "Invalid email or password" in response.text


def test_login_success_sets_cookie_and_grants_access(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="correct-horse-battery")
    response = client.post(
        "/login",
        data={"email": "user@example.com", "password": "correct-horse-battery"},
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert "helpdesk_session" in response.cookies
    assert "csrf_token" in response.cookies

    follow_up = client.get("/api/system/info")
    assert follow_up.status_code == 200


def test_logout_revokes_session(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="correct-horse-battery")
    client.post("/login", data={"email": "user@example.com", "password": "correct-horse-battery"})
    assert client.get("/api/system/info").status_code == 200

    client.post("/logout", data={"csrf_token": client.cookies.get("csrf_token", "")})
    assert client.get("/api/system/info").status_code == 401
