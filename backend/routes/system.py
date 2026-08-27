from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from backend.services.system_service import get_system_info
from backend.services.windows_tools import (
    COMMAND_TOOLS,
    LAUNCH_TOOLS,
    POWER_TOOLS,
    ToolCooldownError,
    cancel_power,
    launch_tool,
    ping_test,
)

router = APIRouter()


class PingRequest(BaseModel):
    host: str = Field(default="8.8.8.8", min_length=1, max_length=255)


@router.get("/info")
def system_info():
    return get_system_info()


@router.get("/tools")
def list_tools():
    return {
        "launch": sorted(LAUNCH_TOOLS.keys()),
        "command": sorted(COMMAND_TOOLS.keys()),
        "power": sorted(POWER_TOOLS.keys()),
    }


@router.post("/tools/{tool_name}")
def open_windows_tool(tool_name: str):
    try:
        return launch_tool(tool_name)
    except ToolCooldownError as exc:
        raise HTTPException(status_code=429, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/ping")
def run_ping(payload: PingRequest):
    try:
        output = ping_test(payload.host.strip())
        return {"status": "ok", "tool": "ping_test", "output": output}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.post("/power/cancel")
def power_cancel():
    output = cancel_power()
    return {"status": "ok", "tool": "cancel_power", "output": output}
