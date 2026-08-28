import json

from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DbSession

from backend.config import BASE_DIR, get_settings
from backend.db.models import AuditLog, Report, User
from backend.services.system_service import get_system_info

_AUDIT_HISTORY_LIMIT = 20
_OUTPUT_PREVIEW_LIMIT = 300
_DISK_WARNING_PERCENT = 80
_RAM_WARNING_PERCENT = 85

# Tools whose successful use counts as a remediation step for the Resolution
# section (as opposed to read-only diagnostics like check_ip/system_logs).
_REMEDIATION_TOOLS = {"dns_flush", "disk_cleanup", "restart", "shutdown", "cancel_power"}

_templates = Jinja2Templates(directory=BASE_DIR / "templates")


def generate_report(db: DbSession, user: User) -> Report:
    system = get_system_info()
    recent_audit = (
        db.query(AuditLog)
        .filter(AuditLog.user_id == user.id)
        .order_by(AuditLog.created_at.desc())
        .limit(_AUDIT_HISTORY_LIMIT)
        .all()
    )
    audit_summary = [
        {
            "tool_name": row.tool_name,
            "category": row.category,
            "success": row.success,
            "exit_code": row.exit_code,
            "error_message": row.error_message,
            "output_preview": (row.output_excerpt or "")[:_OUTPUT_PREVIEW_LIMIT] or None,
            "created_at": row.created_at.isoformat(),
        }
        for row in recent_audit
    ]

    report = Report(
        user_id=user.id,
        computer_name=system["computer_name"],
        os_name=system["os_name"],
        os_subtitle=system["os_subtitle"],
        system_snapshot=json.dumps(system),
        audit_summary=json.dumps(audit_summary),
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reports(db: DbSession, user: User) -> list[Report]:
    return (
        db.query(Report)
        .filter(Report.user_id == user.id)
        .order_by(Report.created_at.desc())
        .all()
    )


def _health_line(system: dict) -> str:
    health = system.get("health") or {}
    status = health.get("status", "Unknown")
    message = health.get("message", "")
    return f"{status} — {message}" if message else status


def _connectivity_issues(system: dict) -> list[str]:
    issues = []
    if not system.get("network_connected"):
        issues.append("Network adapter reports disconnected")
    if not system.get("internet_connected"):
        issues.append("No internet connectivity detected")
    return issues


def _build_sections(system: dict, live_system: dict, audit_summary: list[dict]) -> dict:
    failed = [a for a in audit_summary if not a.get("success", True)]
    succeeded = [a for a in audit_summary if a.get("success", True)]
    health = system.get("health") or {}
    health_level = health.get("level", "good")

    # --- Issue Details ---
    issue_lines = list(_connectivity_issues(system))
    if health_level != "good":
        issue_lines.append(health.get("message", "System health check flagged an issue"))
    for entry in failed:
        issue_lines.append(f"{entry['tool_name']} failed at {entry['created_at']}")
    issue_details = issue_lines or ["No issues detected automatically at the time this report was generated."]

    # --- Findings ---
    findings = [f"{len(audit_summary)} action(s) recorded, {len(succeeded)} succeeded, {len(failed)} failed."]
    if system.get("disk_percent", 0) >= _DISK_WARNING_PERCENT:
        findings.append(f"Disk usage at {system['disk_percent']:.0f}% — approaching capacity.")
    if system.get("ram_percent", 0) >= _RAM_WARNING_PERCENT:
        findings.append(f"Memory usage at {system['ram_percent']:.0f}% — running high.")
    for entry in failed:
        detail = entry.get("error_message") or entry.get("output_preview") or "no further detail captured"
        findings.append(f"'{entry['tool_name']}' did not complete successfully: {detail}")
    if not failed and health_level == "good" and not _connectivity_issues(system):
        findings.append("No anomalies found in system health or recent tool activity.")

    # --- Root Cause ---
    if failed:
        latest = failed[0]
        detail = latest.get("error_message") or latest.get("output_preview") or "no error detail captured"
        root_cause = f"Most recent failure — '{latest['tool_name']}' ({latest['category']}) at {latest['created_at']}: {detail}"
    elif health_level != "good":
        root_cause = health.get("message", "System health check flagged a condition")
    elif _connectivity_issues(system):
        root_cause = "; ".join(_connectivity_issues(system))
    else:
        root_cause = "No root cause identified — no failures or health issues detected in this diagnostic window."

    # --- Resolution ---
    remediations = [a for a in succeeded if a["tool_name"] in _REMEDIATION_TOOLS]
    if remediations:
        names = ", ".join(sorted({a["tool_name"] for a in remediations}))
        resolution = f"Remediation action(s) completed successfully: {names}."
    else:
        resolution = "No remediation action recorded in this session — see Troubleshooting Performed for actions taken."

    # --- Validation (compares generation-time snapshot against a fresh live check) ---
    live_health = live_system.get("health") or {}
    validation = [
        f"Health at time of generation: {_health_line(system)}",
        f"Health as of this download: {_health_line(live_system)}",
    ]
    if health_level != "good" and live_health.get("level") == "good":
        validation.append("Condition appears resolved as of this viewing.")
    elif health_level != "good" and live_health.get("level") == health_level:
        validation.append("Condition is unchanged since generation — may still require attention.")

    # --- Final Status ---
    if live_health.get("level") == "critical" or (failed and live_health.get("level") != "good"):
        final_status = "Unresolved — Escalation Recommended"
    elif live_health.get("level") == "warning":
        final_status = "Monitoring Recommended"
    else:
        final_status = "Resolved — No Issues Detected"

    return {
        "issue_details": issue_details,
        "findings": findings,
        "root_cause": root_cause,
        "resolution": resolution,
        "validation": validation,
        "final_status": final_status,
    }


def render_report_html(report: Report, generated_for: User) -> str:
    system = json.loads(report.system_snapshot)
    audit_summary = json.loads(report.audit_summary)
    live_system = get_system_info()
    sections = _build_sections(system, live_system, audit_summary)
    settings = get_settings()

    template = _templates.get_template("report_document.html")
    return template.render(
        report=report,
        system=system,
        live_system=live_system,
        audit_summary=audit_summary,
        generated_for=generated_for,
        sections=sections,
        ticketing_url=settings.ticketing_url,
    )
