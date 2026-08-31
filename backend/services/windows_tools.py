import os
import subprocess
import time
from typing import Callable

from sqlalchemy.orm import Session as DbSession

from backend.db.models import Role, User
from backend.services.audit_service import record_tool_invocation
from backend.services.system_service import CommandResult, run_command

POWER_COOLDOWN_SECONDS = 60
_last_power_at: dict[str, float] = {}


# All tools are currently open to every authenticated user (2026-08-28,
# explicit user decision): restart/shutdown are normal self-service actions;
# device_manager/services rely on Windows UAC + the AD admin-group policy to
# block non-admin employees from actually changing anything (viewing is
# harmless); cmd is a deliberate exception to that reasoning since it runs
# unelevated with the caller's own permissions and isn't gated by any
# UAC/AD prompt, but the user chose to open it anyway. Kept as a set (rather
# than removed) so a future tool can be restricted without re-plumbing RBAC.
TECHNICIAN_ONLY_TOOLS: set[str] = set()


class ToolCooldownError(Exception):
    """Raised when a power action is retried before its cooldown elapses."""


def _popen(args: list[str], *, new_console: bool = False) -> None:
    flags = 0
    if new_console and hasattr(subprocess, "CREATE_NEW_CONSOLE"):
        flags |= subprocess.CREATE_NEW_CONSOLE
    subprocess.Popen(args, creationflags=flags)


def _startfile(path: str, arguments: str = "") -> None:
    os.startfile(path, arguments=arguments)


def open_system_info() -> None:
    _popen(["msinfo32.exe"])


def open_device_manager() -> None:
    _startfile("devmgmt.msc")


def open_event_viewer() -> None:
    _startfile("eventvwr.msc")


def open_task_manager() -> None:
    _popen(["taskmgr.exe"])


def open_services() -> None:
    _startfile("services.msc")


def open_cmd() -> None:
    _popen(["cmd.exe"], new_console=True)


def open_disk_cleanup() -> None:
    _popen(["cleanmgr.exe"])


def open_windows_update() -> None:
    _popen(["cmd.exe", "/c", "start", "", "ms-settings:windowsupdate"])


def open_reliability_monitor() -> None:
    # perfmon.exe requires elevation on some systems; CreateProcess (Popen) can't
    # trigger the UAC prompt for that, but ShellExecute (os.startfile) can.
    _startfile("perfmon.exe", arguments="/rel")


def open_performance_monitor() -> None:
    _startfile("perfmon.exe")


def open_resource_monitor() -> None:
    _popen(["resmon.exe"])


def flush_dns() -> CommandResult:
    return run_command(["ipconfig", "/flushdns"])


def check_ip_address() -> CommandResult:
    return run_command(["ipconfig", "/all"])


def wifi_information() -> CommandResult:
    result = run_command(["netsh", "wlan", "show", "interfaces"])
    text = result.output.lower()
    if "not running" in text or "there is no wireless" in text:
        profiles = run_command(["netsh", "wlan", "show", "profiles"])
        return CommandResult(
            command=profiles.command,
            returncode=profiles.returncode,
            stdout=f"{result.output}\n\n{profiles.output}",
            duration_ms=result.duration_ms + profiles.duration_ms,
        )
    return result


def ping_test(host: str = "8.8.8.8") -> CommandResult:
    # 20 packets at ~1s each already takes ~19-20s on a healthy link, so a
    # 20s timeout left almost no margin for slower/lossy connections.
    return run_command(["ping", "-n", "20", host], timeout=35)


def system_logs() -> CommandResult:
    return run_command(
        ["wevtutil", "qe", "System", "/c:15", "/rd:true", "/f:text"],
        timeout=40,
    )


def network_logs() -> CommandResult:
    # Microsoft-Windows-NetworkProfile/Operational may not exist on all builds
    result = run_command(
        [
            "wevtutil",
            "qe",
            "Microsoft-Windows-NetworkProfile/Operational",
            "/c:15",
            "/rd:true",
            "/f:text",
        ],
        timeout=40,
    )
    if not result.success:
        return run_command(
            [
                "wevtutil",
                "qe",
                "System",
                "/q:*[System[(EventID=7000 or EventID=7001 or EventID=10000)]]",
                "/c:10",
                "/rd:true",
                "/f:text",
            ],
            timeout=40,
        )
    return result


def performance_logs() -> CommandResult:
    result = run_command(
        [
            "wevtutil",
            "qe",
            "Microsoft-Windows-Diagnostics-Performance/Operational",
            "/c:15",
            "/rd:true",
            "/f:text",
        ],
        timeout=40,
    )
    if "access is denied" in result.output.lower():
        return CommandResult(
            command=result.command,
            returncode=result.returncode,
            stdout=(
                "Access denied reading Microsoft-Windows-Diagnostics-Performance/Operational.\n"
                "This log is restricted to Administrators on this system. "
                "Re-run the IT Helpdesk app elevated (Run as administrator) to view it, "
                "or use Reliability Monitor / Performance Monitor instead."
            ),
            duration_ms=result.duration_ms,
        )
    return result


def restart_pc() -> CommandResult:
    return run_command(["shutdown", "/r", "/t", "5", "/c", "Restart requested from miniOrange ITNexus"])


def shutdown_pc() -> CommandResult:
    return run_command(["shutdown", "/s", "/t", "5", "/c", "Shutdown requested from miniOrange ITNexus"])


def cancel_power() -> CommandResult:
    return run_command(["shutdown", "/a"])


LAUNCH_TOOLS: dict[str, Callable[[], None]] = {
    "system_info": open_system_info,
    "device_manager": open_device_manager,
    "event_viewer": open_event_viewer,
    "task_manager": open_task_manager,
    "services": open_services,
    "cmd": open_cmd,
    "disk_cleanup": open_disk_cleanup,
    "windows_update": open_windows_update,
    "reliability_monitor": open_reliability_monitor,
    "performance_monitor": open_performance_monitor,
    "resource_monitor": open_resource_monitor,
}

COMMAND_TOOLS: dict[str, Callable[..., CommandResult]] = {
    "check_ip": check_ip_address,
    "ping_test": ping_test,
    "wifi_info": wifi_information,
    "dns_flush": flush_dns,
    "system_logs": system_logs,
    "network_logs": network_logs,
    "performance_logs": performance_logs,
    "cancel_power": cancel_power,
}

POWER_TOOLS: dict[str, Callable[[], CommandResult]] = {
    "restart": restart_pc,
    "shutdown": shutdown_pc,
}


def _tool_category(tool_name: str) -> str:
    if tool_name in LAUNCH_TOOLS:
        return "launch"
    if tool_name in COMMAND_TOOLS:
        return "command"
    if tool_name in POWER_TOOLS:
        return "power"
    raise ValueError(f"Unknown tool: {tool_name}")


def launch_tool(
    tool_name: str,
    *,
    user: User,
    db: DbSession,
    ip_address: str | None = None,
    **kwargs,
) -> dict:
    category = _tool_category(tool_name)

    if tool_name in TECHNICIAN_ONLY_TOOLS and user.role != Role.TECHNICIAN:
        raise PermissionError(f"'{tool_name}' requires the technician role")

    start = time.perf_counter()

    if category == "launch":
        try:
            LAUNCH_TOOLS[tool_name]()
            success = True
            error_message = None
            output = f"Opened {tool_name.replace('_', ' ')}."
        except Exception as exc:
            success = False
            error_message = str(exc)
            output = f"Failed to open {tool_name.replace('_', ' ')}: {exc}"
        duration_ms = round((time.perf_counter() - start) * 1000)
        record_tool_invocation(
            db,
            user,
            tool_name=tool_name,
            category=category,
            success=success,
            exit_code=None,
            output=output,
            error_message=error_message,
            duration_ms=duration_ms,
            ip_address=ip_address,
        )
        if not success:
            raise RuntimeError(output)
        return {"status": "ok", "type": "launch", "tool": tool_name, "output": output}

    if category == "command":
        func = COMMAND_TOOLS[tool_name]
        result = func(**kwargs) if kwargs else func()
        duration_ms = round((time.perf_counter() - start) * 1000)
        record_tool_invocation(
            db,
            user,
            tool_name=tool_name,
            category=category,
            success=result.success,
            exit_code=result.returncode,
            output=result.output,
            error_message=result.error,
            duration_ms=duration_ms,
            ip_address=ip_address,
        )
        return {"status": "ok", "type": "command", "tool": tool_name, "output": result.output}

    # category == "power"
    now = time.monotonic()
    last = _last_power_at.get(tool_name)
    if last is not None and (now - last) < POWER_COOLDOWN_SECONDS:
        wait = round(POWER_COOLDOWN_SECONDS - (now - last))
        message = f"{tool_name.title()} was just triggered. Please wait {wait}s before trying again."
        raise ToolCooldownError(message)

    _last_power_at[tool_name] = now
    result = POWER_TOOLS[tool_name]()
    action = "Restart" if tool_name == "restart" else "Shutdown"
    output = (
        f"{action} scheduled in 5 seconds. Run cancel_power to abort."
        if result.success
        else result.output
    )
    duration_ms = round((time.perf_counter() - start) * 1000)
    record_tool_invocation(
        db,
        user,
        tool_name=tool_name,
        category=category,
        success=result.success,
        exit_code=result.returncode,
        output=output,
        error_message=result.error,
        duration_ms=duration_ms,
        ip_address=ip_address,
    )
    return {"status": "ok" if result.success else "error", "type": "power", "tool": tool_name, "output": output}
