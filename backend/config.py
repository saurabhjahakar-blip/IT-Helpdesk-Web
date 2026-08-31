from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BASE_DIR = Path(__file__).resolve().parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=BASE_DIR / ".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = f"sqlite:///{(BASE_DIR / 'data' / 'helpdesk.db').as_posix()}"
    session_cookie_name: str = "helpdesk_session"
    csrf_cookie_name: str = "csrf_token"
    session_ttl_hours: int = 12
    secure_cookies: bool = False
    log_dir: Path = BASE_DIR / "logs"
    ticketing_url: str = "https://itdesk.miniorange.com/raiseTicket"

    host: str = "127.0.0.1"
    port: int = 8000
    ssl_keyfile: str | None = None
    ssl_certfile: str | None = None

    login_rate_limit_attempts: int = 5
    login_rate_limit_window_minutes: int = 15

    # Active Directory / LDAP auth (off by default — existing local accounts
    # keep working until this is explicitly enabled). Values below were
    # confirmed against the real directory on 2026-08-31 via
    # scripts/ldap_diagnose.py.
    ldap_enabled: bool = False
    ldap_domain: str = "ad.xecurify.com"  # internal AD domain — used to connect/search
    ldap_upn_suffix: str = "xecurify.com"  # login suffix, e.g. firstname.lastname@xecurify.com
    ldap_technician_group: str = "it"  # CN=it,OU=Org,OU=Groups,OU=xecurify — confirmed real group
    # LDAPS (636) resets during the TLS handshake in this environment
    # (network security appliance doing SSL inspection is the leading
    # suspect) — plain LDAP (389) binds successfully. This trades
    # confidentiality of the bind for working auth; revisit once whatever's
    # intercepting 636 is identified, or try StartTLS over 389 instead.
    ldap_use_ssl: bool = False


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings
