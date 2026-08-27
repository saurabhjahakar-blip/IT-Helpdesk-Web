import os
import platform
import socket
import subprocess
from datetime import datetime

import psutil

try:
    import winreg
except ImportError:
    winreg = None


def _reg_value(path: str, name: str, default: str = "") -> str:
    if winreg is None:
        return default
    try:
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, path) as key:
            value, _ = winreg.QueryValueEx(key, name)
            return str(value)
    except OSError:
        return default


def _cpu_name() -> str:
    name = _reg_value(
        r"HARDWARE\DESCRIPTION\System\CentralProcessor\0",
        "ProcessorNameString",
        platform.processor() or "Unknown CPU",
    )
    return " ".join(name.split())


def _os_details() -> dict:
    product = _reg_value(
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        "ProductName",
        f"{platform.system()} {platform.release()}",
    )
    display = _reg_value(
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        "DisplayVersion",
        "",
    )
    build = _reg_value(
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        "CurrentBuild",
        platform.version(),
    )
    ubr = _reg_value(
        r"SOFTWARE\Microsoft\Windows NT\CurrentVersion",
        "UBR",
        "",
    )
    build_full = f"{build}.{ubr}" if ubr else build
    subtitle = f"{display} (Build {build_full})" if display else f"Build {build_full}"
    return {
        "os_name": product,
        "os_subtitle": subtitle,
        "os_build": build_full,
    }


def _logged_user() -> str:
    return (
        os.environ.get("USERNAME")
        or os.environ.get("USER")
        or "Unknown"
    )


def _domain() -> str:
    hostname = socket.gethostname()
    domain = os.environ.get("USERDOMAIN") or ""
    if domain and domain.upper() not in {hostname.upper(), _logged_user().upper()}:
        return domain
    try:
        fqdn = socket.getfqdn()
        if "." in fqdn and not fqdn.upper().startswith(hostname.upper() + "."):
            return fqdn.split(".", 1)[1].upper()
    except OSError:
        pass
    return os.environ.get("USERDNSDOMAIN") or "WORKGROUP"


def _network_connected() -> bool:
    addrs = psutil.net_if_addrs()
    stats = psutil.net_if_stats()
    for name, nic_stats in stats.items():
        if not nic_stats.isup:
            continue
        if name.lower().startswith(("loopback", "lo")):
            continue
        for addr in addrs.get(name, []):
            if getattr(addr, "family", None) == socket.AF_INET and not addr.address.startswith("127."):
                return True
    return False


def _internet_connected() -> bool:
    try:
        socket.create_connection(("1.1.1.1", 53), timeout=1.5).close()
        return True
    except OSError:
        return False


def _system_health(disk_percent: float, ram_percent: float) -> dict:
    issues = []
    if disk_percent >= 90:
        issues.append("Disk critically full")
    elif disk_percent >= 80:
        issues.append("Disk usage high")
    if ram_percent >= 90:
        issues.append("Memory critically high")
    elif ram_percent >= 85:
        issues.append("Memory usage high")

    if not issues:
        return {
            "status": "Good",
            "message": "No critical issues found",
            "level": "good",
        }
    if any("critically" in item for item in issues):
        return {
            "status": "Critical",
            "message": "; ".join(issues),
            "level": "critical",
        }
    return {
        "status": "Warning",
        "message": "; ".join(issues),
        "level": "warning",
    }


def get_system_info() -> dict:
    memory = psutil.virtual_memory()
    disk = psutil.disk_usage("C:\\")
    os_info = _os_details()
    cpu_name = _cpu_name()
    freq = psutil.cpu_freq()
    cpu_freq = f"{freq.current / 1000:.2f} GHz" if freq and freq.current else ""
    cpu_subtitle = cpu_freq
    if " @" in cpu_name:
        parts = cpu_name.rsplit(" @", 1)
        cpu_name = parts[0].strip()
        cpu_subtitle = parts[1].strip() if not cpu_subtitle else f"{parts[1].strip()}"

    # Prefer a cleaner subtitle like "12th Gen @ 2.40 GHz" when available
    if "Gen" in cpu_name:
        tokens = cpu_name.split()
        gen_bits = [t for t in tokens if "Gen" in t or t.endswith("th") or t.endswith("nd") or t.endswith("rd") or t.endswith("st")]
        # keep full name; subtitle from freq
        pass

    network_ok = _network_connected()
    internet_ok = _internet_connected()
    health = _system_health(disk.percent, memory.percent)
    now = datetime.now()

    return {
        "computer_name": socket.gethostname(),
        "domain": _domain(),
        "logged_user": _logged_user(),
        "session_active": True,
        "os_name": os_info["os_name"],
        "os_subtitle": os_info["os_subtitle"],
        "cpu_name": cpu_name,
        "cpu_subtitle": cpu_subtitle or f"{psutil.cpu_count(logical=False) or psutil.cpu_count()} cores",
        "cpu_usage": psutil.cpu_percent(interval=0.2),
        "ram_total": round(memory.total / (1024 ** 3), 1),
        "ram_used": round(memory.used / (1024 ** 3), 1),
        "ram_percent": round(memory.percent, 0),
        "disk_total": round(disk.total / (1024 ** 3), 0),
        "disk_used": round(disk.used / (1024 ** 3), 0),
        "disk_percent": round(disk.percent, 0),
        "network_connected": network_ok,
        "internet_connected": internet_ok,
        "health": health,
        "last_updated": now.strftime("%d %b %Y %I:%M:%S %p"),
        "timestamp": now.strftime("%H:%M:%S"),
    }


def run_command(command: list[str], timeout: int = 30) -> str:
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            timeout=timeout,
            shell=False,
            creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
        )
        output = (result.stdout or "") + (result.stderr or "")
        return output.strip() or "Command completed with no output."
    except subprocess.TimeoutExpired:
        return "Command timed out."
    except Exception as exc:
        return f"Error: {exc}"
