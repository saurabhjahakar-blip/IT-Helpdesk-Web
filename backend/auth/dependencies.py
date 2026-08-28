from fastapi import Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session as DbSession

from backend.auth.service import get_session_user
from backend.config import get_settings
from backend.db.models import Role, User
from backend.db.session import get_db

settings = get_settings()


class AuthRedirect(Exception):
    """Raised by page routes to redirect an unauthenticated browser session to /login."""

    def __init__(self, next_path: str):
        self.next_path = next_path


def get_current_user_optional(request: Request, db: DbSession = Depends(get_db)) -> User | None:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        return None
    return get_session_user(db, token)


def require_page_user(request: Request, db: DbSession = Depends(get_db)) -> User:
    user = get_current_user_optional(request, db)
    if user is None:
        raise AuthRedirect(next_path=str(request.url.path))
    return user


def require_api_user(request: Request, db: DbSession = Depends(get_db)) -> User:
    user = get_current_user_optional(request, db)
    if user is None:
        raise HTTPException(status_code=401, detail="Authentication required")
    return user


def require_technician(user: User = Depends(require_api_user)) -> User:
    if user.role != Role.TECHNICIAN:
        raise HTTPException(status_code=403, detail="Technician role required")
    return user


def require_csrf(request: Request) -> None:
    cookie_value = request.cookies.get(settings.csrf_cookie_name)
    header_value = request.headers.get("X-CSRF-Token")
    if not cookie_value or not header_value or cookie_value != header_value:
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")


async def auth_redirect_handler(request: Request, exc: AuthRedirect) -> RedirectResponse:
    return RedirectResponse(url=f"/login?next={exc.next_path}", status_code=303)
