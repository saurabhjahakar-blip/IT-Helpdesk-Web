from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from backend.routes.system import router as system_router
from backend.services.system_service import get_system_info

app = FastAPI(title="miniOrange IT Helpdesk Tool")
app.include_router(system_router, prefix="/api/system", tags=["System"])

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


def _render(request: Request, template: str, active: str, page_title: str, page_subtitle: str, **extra):
    system = get_system_info()
    context = {
        "title": "miniOrange IT Helpdesk Tool",
        "page_title": page_title,
        "page_subtitle": page_subtitle,
        "active_nav": active,
        "nav_items": NAV_ITEMS,
        "system": system,
        **extra,
    }
    return templates.TemplateResponse(request=request, name=template, context=context)


@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return _render(
        request,
        "dashboard.html",
        "dashboard",
        "Dashboard",
        "Overview of your system",
    )


@app.get("/system", response_class=HTMLResponse)
async def system_page(request: Request):
    return _render(
        request,
        "system.html",
        "system",
        "System",
        "System information and Windows tools",
    )


@app.get("/network", response_class=HTMLResponse)
async def network_page(request: Request):
    return _render(
        request,
        "network.html",
        "network",
        "Network",
        "Connectivity, DNS, and Wi-Fi diagnostics",
    )


@app.get("/maintenance", response_class=HTMLResponse)
async def maintenance_page(request: Request):
    return _render(
        request,
        "maintenance.html",
        "maintenance",
        "Maintenance",
        "Cleanup, updates, and power actions",
    )


@app.get("/logs", response_class=HTMLResponse)
async def logs_page(request: Request):
    return _render(
        request,
        "logs.html",
        "logs",
        "Logs & Diagnostics",
        "Event logs and reliability tools",
    )


@app.get("/reports", response_class=HTMLResponse)
async def reports_page(request: Request):
    return _render(
        request,
        "section.html",
        "reports",
        "Reports",
        "Generate a support report",
        section_message="Report generation is planned for a future update. Use the Dashboard and System pages for live diagnostics in the meantime.",
    )


@app.get("/remote", response_class=HTMLResponse)
async def remote_page(request: Request):
    return _render(
        request,
        "section.html",
        "remote",
        "Remote Tools",
        "Remote assistance shortcuts",
        section_message="Connect remote support tools from here in a future update. Quick Access on the Dashboard covers local tools now.",
    )


@app.get("/assets", response_class=HTMLResponse)
async def assets_page(request: Request):
    return _render(
        request,
        "section.html",
        "assets",
        "Asset Management",
        "Track devices and inventory",
        section_message="Asset management placeholders are available. Live hardware details are shown on the Dashboard.",
    )


@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    return _render(
        request,
        "section.html",
        "settings",
        "Settings",
        "Application preferences",
        section_message="Use the theme toggle in the top bar to switch light/dark mode. Preferences are saved in this browser.",
    )


@app.get("/about", response_class=HTMLResponse)
async def about_page(request: Request):
    return _render(
        request,
        "section.html",
        "about",
        "About",
        "miniOrange IT Helpdesk Tool",
        section_message="Version 1.0.0 — Local Windows helpdesk dashboard for system diagnostics, network checks, and maintenance actions.",
    )
