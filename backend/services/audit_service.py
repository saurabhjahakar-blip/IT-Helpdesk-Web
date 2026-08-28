from sqlalchemy.orm import Session as DbSession

from backend.db.models import AuditLog, User
from backend.logging_config import get_audit_logger

_OUTPUT_EXCERPT_LIMIT = 4000

_audit_logger = get_audit_logger()


def record_tool_invocation(
    db: DbSession,
    user: User,
    *,
    tool_name: str,
    category: str,
    success: bool,
    exit_code: int | None,
    output: str,
    error_message: str | None,
    duration_ms: int,
    ip_address: str | None,
) -> None:
    excerpt = (output or "")[:_OUTPUT_EXCERPT_LIMIT]

    fields = {
        "user_id": user.id,
        "username": user.email,
        "tool_name": tool_name,
        "category": category,
        "success": success,
        "exit_code": exit_code,
        "duration_ms": duration_ms,
        "ip_address": ip_address,
        "error_message": error_message,
    }

    # File log is written unconditionally, independent of DB health, so the
    # trail survives a DB outage.
    _audit_logger.info("", extra={"audit_fields": fields})

    try:
        db.add(
            AuditLog(
                user_id=user.id,
                username_snapshot=user.email,
                tool_name=tool_name,
                category=category,
                success=success,
                exit_code=exit_code,
                output_excerpt=excerpt,
                error_message=error_message,
                duration_ms=duration_ms,
                ip_address=ip_address,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
