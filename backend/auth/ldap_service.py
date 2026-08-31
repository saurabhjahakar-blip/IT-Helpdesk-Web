from dataclasses import dataclass
from typing import Callable

from ldap3 import ALL, SIMPLE, Connection, Server
from ldap3.core.exceptions import LDAPException

from backend.config import get_settings

settings = get_settings()


@dataclass(slots=True)
class LdapUserInfo:
    email: str
    display_name: str
    is_technician: bool


def _base_dn(domain: str) -> str:
    return ",".join(f"DC={part}" for part in domain.split("."))


def _default_connection_factory(user_dn: str, password: str) -> Connection:
    server = Server(settings.ldap_domain, use_ssl=settings.ldap_use_ssl, get_info=ALL)
    return Connection(server, user=user_dn, password=password, authentication=SIMPLE, auto_bind=True)


def authenticate_ldap(
    username: str,
    password: str,
    *,
    connection_factory: Callable[[str, str], Connection] = _default_connection_factory,
) -> LdapUserInfo | None:
    """Bind directly as the user (UPN-style) against AD, then read their own
    attributes to determine email/display name/role. Returns None on any
    failure — wrong password, unknown user, or AD unreachable are all
    indistinguishable from the caller's point of view (auth just failed)."""
    if not password:
        return None

    # AD often uses a shorter, email-style UPN suffix (e.g. xecurify.com) that
    # differs from the internal domain used to actually connect (ad.xecurify.com)
    # — both are valid within the same forest, so a bind against ldap_domain's
    # DC with a ldap_upn_suffix-style UPN works fine.
    upn = username if "@" in username else f"{username}@{settings.ldap_upn_suffix}"

    try:
        conn = connection_factory(upn, password)
    except LDAPException:
        return None

    try:
        found = conn.search(
            search_base=_base_dn(settings.ldap_domain),
            search_filter=f"(userPrincipalName={upn})",
            attributes=["mail", "displayName", "memberOf", "userPrincipalName"],
        )
        if not found or not conn.entries:
            return None

        entry = conn.entries[0]
        email = str(entry.mail) if "mail" in entry and entry.mail else upn
        display_name = str(entry.displayName) if "displayName" in entry and entry.displayName else username
        member_of = [str(dn) for dn in entry.memberOf] if "memberOf" in entry else []
        is_technician = any(
            f"cn={settings.ldap_technician_group}".lower() in dn.lower() for dn in member_of
        )
        return LdapUserInfo(email=email.lower(), display_name=display_name, is_technician=is_technician)
    except LDAPException:
        return None
    finally:
        conn.unbind()
