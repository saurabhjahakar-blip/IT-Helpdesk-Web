import time

from backend.config import get_settings

settings = get_settings()

# In-memory, per-process — same pattern as the power-action cooldown in
# windows_tools.py. Consistent with this app's current single-worker
# production launch (see run_prod.bat); moving this to the DB is only
# needed if that assumption changes.
_failed_attempts: dict[str, list[float]] = {}


def _key(email: str, ip_address: str | None) -> str:
    return f"{email.strip().lower()}:{ip_address or 'unknown'}"


def _window_seconds() -> int:
    return settings.login_rate_limit_window_minutes * 60


def is_locked_out(email: str, ip_address: str | None) -> bool:
    key = _key(email, ip_address)
    now = time.monotonic()
    attempts = [t for t in _failed_attempts.get(key, []) if now - t < _window_seconds()]
    _failed_attempts[key] = attempts
    return len(attempts) >= settings.login_rate_limit_attempts


def record_failure(email: str, ip_address: str | None) -> None:
    key = _key(email, ip_address)
    _failed_attempts.setdefault(key, []).append(time.monotonic())


def reset(email: str, ip_address: str | None) -> None:
    _failed_attempts.pop(_key(email, ip_address), None)
