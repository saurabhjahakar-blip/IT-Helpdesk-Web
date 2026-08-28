import pytest

from backend.auth import rate_limit
from backend.config import get_settings
from backend.db.models import Role


@pytest.fixture(autouse=True)
def _reset_rate_limit_state():
    rate_limit._failed_attempts.clear()
    yield
    rate_limit._failed_attempts.clear()


def test_lockout_after_max_failed_attempts(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="correct-pass1")
    limit = get_settings().login_rate_limit_attempts

    for _ in range(limit):
        response = client.post("/login", data={"email": "user@example.com", "password": "wrong"})
        assert response.status_code == 401

    locked = client.post("/login", data={"email": "user@example.com", "password": "correct-pass1"})
    assert locked.status_code == 401
    assert "Too many failed attempts" in locked.text


def test_successful_login_resets_the_counter(client, make_user):
    make_user("user@example.com", Role.EMPLOYEE, password="correct-pass1")

    client.post("/login", data={"email": "user@example.com", "password": "wrong"})
    ok = client.post("/login", data={"email": "user@example.com", "password": "correct-pass1"}, follow_redirects=False)
    assert ok.status_code == 303
    assert rate_limit.is_locked_out("user@example.com", None) is False


def test_lockout_is_scoped_to_the_key_not_global(client, make_user):
    make_user("victim@example.com", Role.EMPLOYEE, password="correct-pass1")
    limit = get_settings().login_rate_limit_attempts

    for _ in range(limit):
        client.post("/login", data={"email": "attacker@example.com", "password": "wrong"})

    # A different account is unaffected by another account's failed attempts.
    response = client.post("/login", data={"email": "victim@example.com", "password": "correct-pass1"}, follow_redirects=False)
    assert response.status_code == 303
