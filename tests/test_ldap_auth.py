import pytest
from ldap3 import MOCK_SYNC, OFFLINE_AD_2012_R2, Connection, Server
from ldap3.core.exceptions import LDAPBindError, LDAPException

from backend.auth.ldap_service import authenticate_ldap
from backend.auth.service import authenticate_user
from backend.config import get_settings
from backend.db.models import Role, User

settings = get_settings()


_UPN_TO_DN = {
    "jane@ad.xecurify.com": "CN=Jane Doe,OU=Users,DC=ad,DC=xecurify,DC=com",
    "bob@ad.xecurify.com": "CN=Bob Smith,OU=Users,DC=ad,DC=xecurify,DC=com",
}


def _mock_directory():
    server = Server("ad.xecurify.com", get_info=OFFLINE_AD_2012_R2)
    conn = Connection(server, client_strategy=MOCK_SYNC)
    conn.open()
    conn.strategy.add_entry(
        _UPN_TO_DN["jane@ad.xecurify.com"],
        {
            "userPassword": "correct-pass1",
            "mail": "jane@xecurify.com",
            "displayName": "Jane Doe",
            "userPrincipalName": "jane@ad.xecurify.com",
            "memberOf": ["CN=IT-Technicians,OU=Groups,DC=ad,DC=xecurify,DC=com"],
        },
    )
    conn.strategy.add_entry(
        _UPN_TO_DN["bob@ad.xecurify.com"],
        {
            "userPassword": "correct-pass2",
            "mail": "bob@xecurify.com",
            "displayName": "Bob Smith",
            "userPrincipalName": "bob@ad.xecurify.com",
            "memberOf": [],
        },
    )
    return conn


def _factory_for(conn):
    # Real AD accepts a simple bind directly against a UPN (user@domain) —
    # that's what backend/auth/ldap_service.py's real connection factory
    # relies on. ldap3's MOCK_SYNC directory only matches bind identities
    # against an entry's actual DN, so this test factory does the UPN->DN
    # resolution a real AD server would do internally, to isolate the test
    # from that mock limitation rather than our code's own logic.
    def factory(upn, password):
        dn = _UPN_TO_DN.get(upn, upn)
        conn.rebind(user=dn, password=password)
        if not conn.bound:
            raise LDAPBindError("bind failed")
        return conn

    return factory


def _unreachable_factory(user_dn, password):
    raise LDAPException("server unreachable")


def test_successful_bind_returns_user_info_with_technician_role():
    conn = _mock_directory()
    info = authenticate_ldap("jane", "correct-pass1", connection_factory=_factory_for(conn))
    assert info is not None
    assert info.email == "jane@xecurify.com"
    assert info.display_name == "Jane Doe"
    assert info.is_technician is True


def test_successful_bind_non_technician_group_gives_employee_role():
    conn = _mock_directory()
    info = authenticate_ldap("bob", "correct-pass2", connection_factory=_factory_for(conn))
    assert info is not None
    assert info.is_technician is False


def test_wrong_password_returns_none():
    conn = _mock_directory()
    info = authenticate_ldap("jane", "wrong-password", connection_factory=_factory_for(conn))
    assert info is None


def test_unknown_user_returns_none():
    conn = _mock_directory()
    info = authenticate_ldap("nobody", "whatever", connection_factory=_factory_for(conn))
    assert info is None


def test_ldap_unreachable_returns_none():
    info = authenticate_ldap("jane", "correct-pass1", connection_factory=_unreachable_factory)
    assert info is None


def test_empty_password_returns_none_without_binding():
    called = []

    def factory(user_dn, password):
        called.append(True)
        raise AssertionError("should not attempt to bind with an empty password")

    info = authenticate_ldap("jane", "", connection_factory=factory)
    assert info is None
    assert called == []


# --- authenticate_user() JIT provisioning + local break-glass fallback ---


def test_jit_provisions_new_user_on_first_ldap_login(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ldap_enabled", True)
    conn = _mock_directory()
    monkeypatch.setattr(
        "backend.auth.service.authenticate_ldap",
        lambda username, password, **kw: authenticate_ldap(username, password, connection_factory=_factory_for(conn)),
    )

    assert db_session.query(User).filter(User.email == "jane@xecurify.com").first() is None
    user = authenticate_user(db_session, "jane", "correct-pass1")
    assert user is not None
    assert user.auth_source == "ldap"
    assert user.role == Role.TECHNICIAN
    assert user.password_hash is None


def test_ldap_failure_falls_back_to_local_breakglass_only(db_session, monkeypatch):
    monkeypatch.setattr(settings, "ldap_enabled", True)
    monkeypatch.setattr("backend.auth.service.authenticate_ldap", lambda *a, **kw: None)

    from backend.security import hash_password

    local_admin = User(
        email="admin@company.local",
        display_name="Break Glass",
        password_hash=hash_password("adminpass1"),
        auth_source="local",
        role=Role.TECHNICIAN,
    )
    db_session.add(local_admin)
    db_session.commit()

    # Local break-glass account still works when LDAP is enabled but the bind failed.
    assert authenticate_user(db_session, "admin@company.local", "adminpass1") is not None

    # A regular (non-local) account with no usable password never falls through.
    ldap_user = User(
        email="ldapuser@xecurify.com",
        display_name="LDAP User",
        password_hash=None,
        auth_source="ldap",
        role=Role.EMPLOYEE,
    )
    db_session.add(ldap_user)
    db_session.commit()
    assert authenticate_user(db_session, "ldapuser@xecurify.com", "anything") is None
