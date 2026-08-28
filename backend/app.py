from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DbSession

from backend.auth.dependencies import AuthRedirect, auth_redirect_handler, require_page_user
from backend.db.models import AuditLog, Role, User
from backend.db.session import get_db
from backend.logging_config import configure_logging
from backend.routes.account import router as account_router
from backend.routes.assets import router as assets_router
from backend.routes.auth import router as auth_router
from backend.routes.reports import router as reports_router
from backend.routes.system import router as system_router
from backend.services.asset_service import list_snapshots
from backend.services.report_service import list_reports
from backend.services.system_service import get_system_info

_SETTINGS_ACTIVITY_LIMIT = 50


@asynccontextmanager
async def _lifespan(app: FastAPI):
    configure_logging()
    yield


app = FastAPI(title="miniOrange IT Helpdesk Tool", lifespan=_lifespan)
app.add_exception_handler(AuthRedirect, auth_redirect_handler)
app.include_router(auth_router, tags=["Auth"])
app.include_router(system_router, prefix="/api/system", tags=["System"])
app.include_router(reports_router, prefix="/api/reports", tags=["Reports"])
app.include_router(assets_router, prefix="/api/assets", tags=["Assets"])
app.include_router(account_router, prefix="/api/account", tags=["Account"])

BASE_DIR = Path(__file__).resolve().parent.parent

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=BASE_DIR / "templates")

NAV_ITEMS = [
    {"id": "dashboard", "label": "Dashboard", "icon": "bi-speedometer2", "path": "/"},
    {"id": "system", "label": "System", "icon": "bi-pc-display", "path": "/system"},
    {"id": "network", "label": "Network", "icon": "bi-wifi", "path": "/network"},
    {"id": "maintenance", "label": "Maintenance", "icon": "bi-tools", "path": "/maintenance"},
    {"id": "logs", "label": "Logs & Diagnostics", "icon": "bi-clipboard2-pulse", "path": "/logs"},
    {"id": "reports", "label": "Reports", "icon": "bi-bar-chart", "path": "/reports"},
    {"id": "remote", "label": "Remote Tools", "icon": "bi-display", "path": "/remote"},
    {"id": "assets", "label": "Asset Management", "icon": "bi-box-seam", "path": "/assets"},
    {"id": "settings", "label": "Settings", "icon": "bi-gear", "path": "/settings"},
    {"id": "about", "label": "About", "icon": "bi-info-circle", "path": "/about"},
]


def _render(request: Request, template: str, active: str, page_title: str, page_subtitle: str, user: User, **extra):
    system = get_system_info()
    context = {
        "title": "miniOrange IT Helpdesk Tool",
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "active_nav": active,
        "nav_items": NAV_ITEMS,
        "system": system,
        "current_user": user,
        **extra,
    }
    return templates.TemplateResponse(request=request, name=template, context=context)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request, user: User = Depends(require_page_user)):
    return _render(
        request,
        "dashboard.html",
        "dashboard",
        "Dashboard",
        "Overview of your system",
        user,
    )


@app.get("/system", response_class=HTMLResponse)
async def system_page(request: Request, user: User = Depends(require_page_user)):
    return _render(
        request,
        "system.html",
        "system",
        "System",
        "System information and Windows tools",
        user,
    )


@app.get("/network", response_class=HTMLResponse)
async def network_page(request: Request, user: User = Depends(require_page_user)):
    return _render(
        request,
        "network.html",
        "network",
        "Network",
        "Connectivity, DNS, and Wi-Fi diagnostics",
        user,
    )


@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance_page(request: Request, user: User = Depends(require_page_user)):
    return _render(
        request,
        "maintenance.html",
        "maintenance",
        "Maintenance",
        "Cleanup, updates, and power actions",
        user,
    )


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request, user: User = Depends(require_page_user)):
    return _render(
        request,
        "logs.html",
        "logs",
        "Logs & Diagnostics",
        "Event logs and reliability tools",
        user,
    )


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(
    request: Request, user: User = Depends(require_page_user), db: DbSession = Depends(get_db)
):
    return _render(
        request,
        "reports.html",
        "reports",
        "Reports",
        "Generate a support report",
        user,
        reports=list_reports(db, user),
    )


@app.get("/remote", response_class=HTMLResponse)
async def remote_page(request: Request, user: User = Depends(require_page_user)):
    return _render(
        request,
        "section.html",
        "remote",
        "Remote Tools",
        "Remote assistance shortcuts",
        user,
        section_message="Fleet-wide remote control ships with the exe/agent rollout in Phase 3 — each machine's agent will report to a central server so a technician can reach it remotely. This page is a placeholder until then.",
    )


@app.get("/assets", response_class=HTMLResponse)
async def assets_page(
    request: Request, user: User = Depends(require_page_user), db: DbSession = Depends(get_db)
):
    return _render(
        request,
        "assets.html",
        "assets",
        "Asset Management",
        "Hardware and OS snapshot history for this machine",
        user,
        snapshots=list_snapshots(db),
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(
    request: Request, user: User = Depends(require_page_user), db: DbSession = Depends(get_db)
):
    activity = None
    if user.role == Role.TECHNICIAN:
        activity = (
            db.query(AuditLog)
            .order_by(AuditLog.created_at.desc())
            .limit(_SETTINGS_ACTIVITY_LIMIT)
            .all()
        )
    return _render(
        request,
        "settings.html",
        "settings",
        "Settings",
        "Application preferences",
        user,
        activity=activity,
    )


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request, user: User = Depends(require_page_user)):
    return _render(
        request,
        "section.html",
        "about",
        "About",
        "miniOrange IT Helpdesk Tool",
        user,
        section_message="Version 1.0.0 — Local Windows helpdesk dashboard for system diagnostics, network checks, and maintenance actions.",
    )
