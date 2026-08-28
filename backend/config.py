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
    # keep working until this is explicitly enabled with confirmed values).
    ldap_enabled: bool = False
    ldap_domain: str = "ad.xecurify.com"
    ldap_technician_group: str = "IT-Technicians"
    ldap_use_ssl: bool = True


@lru_cache
def get_settings() -> Settings:
    settings = Settings()
    if settings.database_url.startswith("sqlite:///"):
        db_path = Path(settings.database_url.removeprefix("sqlite:///"))
        db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.log_dir.mkdir(parents=True, exist_ok=True)
    return settings
