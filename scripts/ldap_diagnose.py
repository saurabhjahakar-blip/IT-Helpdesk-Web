"""Standalone LDAP bind diagnostic — run this yourself (it needs your real
password, typed into your own terminal, not shared anywhere) to see the
*actual* AD error instead of the app's generic "invalid credentials".

Usage:
    python scripts/ldap_diagnose.py
    (prompts for username and password)
"""

import getpass
import socket
import sys
from pathlib import Path

# Allow running directly as `python scripts/ldap_diagnose.py` regardless of
# cwd — Python only puts the script's own directory on sys.path by default,
# not the repo root, so `backend` wouldn't otherwise be importable.
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from ldap3 import ALL, SIMPLE, Connection, Server
from ldap3.core.exceptions import LDAPException

from backend.config import get_settings


def _try_bind(domain: str, upn: str, password: str, *, use_ssl: bool, technician_group: str) -> None:
    port = 636 if use_ssl else 389
    label = "LDAPS (636, encrypted)" if use_ssl else "plain LDAP (389, unencrypted)"
    print(f"\n--- {label} bind as {upn} ---")
    try:
        server = Server(domain, port=port, use_ssl=use_ssl, get_info=ALL, connect_timeout=10)
        conn = Connection(server, user=upn, password=password, authentication=SIMPLE, raise_exceptions=False)
        bound = conn.bind()
        print(f"bind() returned: {bound}")
        print(f"connection.result: {conn.result}")
        if not bound:
            print(
                "Common AD data codes: 52e=bad password, 525=user not found, "
                "530=logon time restriction, 531=workstation restriction, "
                "532=password expired, 533=account disabled, 701=account expired, "
                "773=must change password at next logon, 775=account locked out."
            )
            return

        print("Bind succeeded — searching for own entry...")
        base_dn = ",".join(f"DC={part}" for part in domain.split("."))
        found = conn.search(
            search_base=base_dn,
            search_filter=f"(userPrincipalName={upn})",
            attributes=["mail", "displayName", "memberOf", "userPrincipalName"],
        )
        print(f"search found: {found}, entries: {len(conn.entries)}")
        if conn.entries:
            entry = conn.entries[0]
            print(f"entry DN: {entry.entry_dn}")
            print(f"mail: {entry.mail if 'mail' in entry else '(not set)'}")
            print(f"displayName: {entry.displayName if 'displayName' in entry else '(not set)'}")
            member_of = list(entry.memberOf) if "memberOf" in entry else []
            print(f"memberOf ({len(member_of)} groups):")
            for dn in member_of:
                print(f"  - {dn}")
            is_tech = any(f"cn={technician_group}".lower() in dn.lower() for dn in member_of)
            print(f"Would map to role: {'technician' if is_tech else 'employee'}")
        else:
            print(
                f"No entry found via userPrincipalName search — the search_base ({base_dn}) "
                "or the userPrincipalName attribute value may not match what's actually in AD."
            )
        conn.unbind()
    except LDAPException as exc:
        print(f"LDAPException: {exc}")
    except Exception as exc:
        print(f"Unexpected error: {exc!r}")


def main() -> None:
    settings = get_settings()
    print(f"ldap_domain:           {settings.ldap_domain}")
    print(f"ldap_upn_suffix:       {settings.ldap_upn_suffix}")
    print(f"ldap_technician_group: {settings.ldap_technician_group}")

    username = input("\nUsername (bare, e.g. firstname.lastname): ").strip()
    password = getpass.getpass("Password: ")
    upn = username if "@" in username else f"{username}@{settings.ldap_upn_suffix}"
    print(f"\nWill bind as: {upn}")

    print(f"\n--- DNS resolution of {settings.ldap_domain} ---")
    try:
        print(socket.gethostbyname_ex(settings.ldap_domain))
    except Exception as exc:
        print(f"FAILED: {exc}")

    for port in (636, 389):
        print(f"\n--- TCP connect to {settings.ldap_domain}:{port} ---")
        try:
            with socket.create_connection((settings.ldap_domain, port), timeout=5):
                print("OK")
        except Exception as exc:
            print(f"FAILED: {exc}")

    # Try both encrypted and plaintext — if plaintext works and LDAPS doesn't,
    # that isolates the problem to TLS negotiation specifically (e.g. a
    # network security device doing SSL inspection) rather than credentials
    # or basic reachability.
    _try_bind(settings.ldap_domain, upn, password, use_ssl=True, technician_group=settings.ldap_technician_group)
    _try_bind(settings.ldap_domain, upn, password, use_ssl=False, technician_group=settings.ldap_technician_group)


if __name__ == "__main__":
    main()
