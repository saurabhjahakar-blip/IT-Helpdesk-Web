import os
import subprocess
import time
from typing import Callable

from backend.services.system_service import run_command

POWER_COOLDOWN_SECONDS = 60
_last_power_at: dict[str, float] = {}


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


def flush_dns() -> str:
    return run_command(["ipconfig", "/flushdns"])


def check_ip_address() -> str:
    return run_command(["ipconfig", "/all"])


def wifi_information() -> str:
    output = run_command(["netsh", "wlan", "show", "interfaces"])
    if "not running" in output.lower() or "there is no wireless" in output.lower():
        profiles = run_command(["netsh", "wlan", "show", "profiles"])
        return f"{output}\n\n{profiles}"
    return output


def ping_test(host: str = "8.8.8.8") -> str:
    return run_command(["ping", "-n", "20", host], timeout=20)



def system_logs() -> str:
    return run_command(
        [
            "wevtutil",
            "qe",
            "System",
            "/c:15",
            "/rd:true",
            "/f:text",
        ],
        timeout=40,
    )


def network_logs() -> str:
    # Microsoft-Windows-NetworkProfile/Operational may not exist on all builds
    output = run_command(
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
    if output.lower().startswith("error"):
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
    return output


def performance_logs() -> str:
    output = run_command(
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
    if "access is denied" in output.lower():
        return (
            "Access denied reading Microsoft-Windows-Diagnostics-Performance/Operational.\n"
            "This log is restricted to Administrators on this system. "
            "Re-run the IT Helpdesk app elevated (Run as administrator) to view it, "
            "or use Reliability Monitor / Performance Monitor instead."
        )
    return output


def restart_pc() -> None:
    subprocess.Popen(["shutdown", "/r", "/t", "5", "/c", "Restart requested from miniOrange IT Helpdesk"])


def shutdown_pc() -> None:
    subprocess.Popen(["shutdown", "/s", "/t", "5", "/c", "Shutdown requested from miniOrange IT Helpdesk"])


def cancel_power() -> str:
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

COMMAND_TOOLS: dict[str, Callable[[], str]] = {
    "check_ip": check_ip_address,
    "ping_test": ping_test,
    "wifi_info": wifi_information,
    "dns_flush": flush_dns,
    "system_logs": system_logs,
    "network_logs": network_logs,
    "performance_logs": performance_logs,
    "cancel_power": cancel_power,
}

POWER_TOOLS: dict[str, Callable[[], None]] = {
    "restart": restart_pc,
    "shutdown": shutdown_pc,
}

# Backwards-compatible alias used by older routes
TOOLS = {**LAUNCH_TOOLS, **COMMAND_TOOLS, **POWER_TOOLS}


def launch_tool(tool_name: str) -> dict:
    if tool_name in LAUNCH_TOOLS:
        LAUNCH_TOOLS[tool_name]()
        output = f"Opened {tool_name.replace('_', ' ')}."
        return {"status": "ok", "type": "launch", "tool": tool_name, "output": output}

    if tool_name in COMMAND_TOOLS:
        output = COMMAND_TOOLS[tool_name]()
        return {"status": "ok", "type": "command", "tool": tool_name, "output": output}

    if tool_name in POWER_TOOLS:
        now = time.monotonic()
        last = _last_power_at.get(tool_name)
        if last is not None and (now - last) < POWER_COOLDOWN_SECONDS:
            wait = round(POWER_COOLDOWN_SECONDS - (now - last))
            message = f"{tool_name.title()} was just triggered. Please wait {wait}s before trying again."
            raise ToolCooldownError(message)

        _last_power_at[tool_name] = now
        POWER_TOOLS[tool_name]()
        action = "Restart" if tool_name == "restart" else "Shutdown"
        output = f"{action} scheduled in 5 seconds. Run cancel_power to abort."
        return {"status": "ok", "type": "power", "tool": tool_name, "output": output}

    raise ValueError(f"Unknown tool: {tool_name}")
