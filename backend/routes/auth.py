from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DbSession

from backend.auth import rate_limit
from backend.auth.dependencies import get_current_user_optional
from backend.auth.service import authenticate_user, create_session, revoke_session
from backend.config import BASE_DIR, get_settings
from backend.db.models import User
from backend.db.session import get_db
from backend.security import generate_csrf_token
from backend.services.audit_service import record_auth_event

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "templates")
settings = get_settings()


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = "/", db: DbSession = Depends(get_db)):
    if get_current_user_optional(request, db) is not None:
        return RedirectResponse(url=next or "/", status_code=303)
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={"title": "Sign in", "next": next, "error": None},
    )


@router.post("/login", response_class=HTMLResponse)
def login_submit(
    request: Request,
    email: str = Form(...),
    password: str = Form(...),
    next: str = Form("/"),
    db: DbSession = Depends(get_db),
):
    ip_address = _client_ip(request)
    identifier = email.strip().lower()

    if rate_limit.is_locked_out(identifier, ip_address):
        record_auth_event(
            db, user_id=None, username_snapshot=identifier, event="login_lockout", success=False, ip_address=ip_address
        )
        wait_minutes = settings.login_rate_limit_window_minutes
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "title": "Sign in",
                "next": next,
                "error": f"Too many failed attempts. Try again in up to {wait_minutes} minutes.",
            },
            status_code=401,
        )

    user = authenticate_user(db, email, password)
    if user is None:
        rate_limit.record_failure(identifier, ip_address)
        record_auth_event(
            db, user_id=None, username_snapshot=identifier, event="login_failure", success=False, ip_address=ip_address
        )
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"title": "Sign in", "next": next, "error": "Invalid email or password."},
            status_code=401,
        )

    rate_limit.reset(identifier, ip_address)
    record_auth_event(
        db, user_id=user.id, username_snapshot=user.email, event="login_success", success=True, ip_address=ip_address
    )

    token = create_session(
        db,
        user,
        ip_address=ip_address,
        user_agent=request.headers.get("user-agent"),
    )
    csrf_token = generate_csrf_token()
    response = RedirectResponse(url=next or "/", status_code=303)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        max_age=settings.session_ttl_hours * 3600,
    )
    response.set_cookie(
        key=settings.csrf_cookie_name,
        value=csrf_token,
        httponly=False,
        samesite="lax",
        secure=settings.secure_cookies,
        max_age=settings.session_ttl_hours * 3600,
    )
    return response


@router.post("/logout")
def logout(
    request: Request,
    csrf_token: str = Form(default=""),
    user: User | None = Depends(get_current_user_optional),
    db: DbSession = Depends(get_db),
):
    cookie_csrf = request.cookies.get(settings.csrf_cookie_name, "")
    if not cookie_csrf or cookie_csrf != csrf_token:
        raise HTTPException(status_code=403, detail="Missing or invalid CSRF token")

    token = request.cookies.get(settings.session_cookie_name)
    if token:
        revoke_session(db, token)
    if user is not None:
        record_auth_event(
            db, user_id=user.id, username_snapshot=user.email, event="logout", success=True, ip_address=_client_ip(request)
        )
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    response.delete_cookie(settings.csrf_cookie_name)
    return response
