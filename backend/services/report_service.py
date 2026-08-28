import json

from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session as DbSession

from backend.config import BASE_DIR
from backend.db.models import AuditLog, Report, User
from backend.services.system_service import get_system_info

_AUDIT_HISTORY_LIMIT = 20
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


def render_report_html(report: Report, generated_for: User) -> str:
    template = _templates.get_template("report_document.html")
    return template.render(
        report=report,
        system=json.loads(report.system_snapshot),
        audit_summary=json.loads(report.audit_summary),
        generated_for=generated_for,
    )
