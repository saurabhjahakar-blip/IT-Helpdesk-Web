from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DbSession

from backend.auth.dependencies import get_current_user_optional
from backend.auth.service import authenticate_user, create_session, revoke_session
from backend.config import BASE_DIR, get_settings
from backend.db.session import get_db

router = APIRouter()
templates = Jinja2Templates(directory=BASE_DIR / "templates")
settings = get_settings()


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
    user = authenticate_user(db, email, password)
    if user is None:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={"title": "Sign in", "next": next, "error": "Invalid email or password."},
            status_code=401,
        )

    token = create_session(
        db,
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    response = RedirectResponse(url=next or "/", status_code=303)
    response.set_cookie(
        key=settings.session_cookie_name,
        value=token,
        httponly=True,
        samesite="lax",
        secure=settings.secure_cookies,
        max_age=settings.session_ttl_hours * 3600,
    )
    return response


@router.post("/logout")
def logout(request: Request, db: DbSession = Depends(get_db)):
    token = request.cookies.get(settings.session_cookie_name)
    if token:
        revoke_session(db, token)
    response = RedirectResponse(url="/login", status_code=303)
    response.delete_cookie(settings.session_cookie_name)
    return response
