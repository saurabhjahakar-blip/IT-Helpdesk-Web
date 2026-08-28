from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from backend.auth.dependencies import require_api_user
from backend.db.models import Role, User
from backend.db.session import get_db
from backend.services.system_service import get_system_info
from backend.services.windows_tools import (
    COMMAND_TOOLS,
    LAUNCH_TOOLS,
    POWER_TOOLS,
    TECHNICIAN_ONLY_TOOLS,
    ToolCooldownError,
    launch_tool,
)

router = APIRouter()


class PingRequest(BaseModel):
    host: str = Field(default="8.8.8.8", min_length=1, max_length=255)


def _client_ip(request: Request) -> str | None:
    return request.client.host if request.client else None


@router.get("/info")
def system_info(user: User = Depends(require_api_user)):
    return get_system_info()


@router.get("/tools")
def list_tools(user: User = Depends(require_api_user)):
    def _visible(names: list[str]) -> list[str]:
        if user.role == Role.TECHNICIAN:
            return sorted(names)
        return sorted(n for n in names if n not in TECHNICIAN_ONLY_TOOLS)

    return {
        "launch": _visible(LAUNCH_TOOLS.keys()),
        "command": _visible(COMMAND_TOOLS.keys()),
        "power": _visible(POWER_TOOLS.keys()),
    }


@router.post("/tools/{tool_name}")
def open_windows_tool(
    tool_name: str,
    request: Request,
    user: User = Depends(require_api_user),
    db: DbSession = Depends(get_db),
):
    try:
        return launch_tool(tool_name, user=user, db=db, ip_address=_client_ip(request))
    except ToolCooldownError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ping")
def run_ping(
    payload: PingRequest,
    request: Request,
    user: User = Depends(require_api_user),
    db: DbSession = Depends(get_db),
):
    try:
        return launch_tool(
            "ping_test",
            user=user,
            db=db,
            ip_address=_client_ip(request),
            host=payload.host.strip(),
        )
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/power/cancel")
def power_cancel(
    request: Request,
    user: User = Depends(require_api_user),
    db: DbSession = Depends(get_db),
):
    try:
        return launch_tool("cancel_power", user=user, db=db, ip_address=_client_ip(request))
    except PermissionError as exc:
        raise HTTPException(status_code=403, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
