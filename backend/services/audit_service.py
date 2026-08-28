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


def record_auth_event(
    db: DbSession,
    *,
    user_id: int | None,
    username_snapshot: str,
    event: str,
    success: bool,
    ip_address: str | None,
) -> None:
    """Login/logout/lockout events — a security-review gap `record_tool_invocation`
    doesn't cover, since it requires an already-authenticated User. `user_id` is
    None for a failed attempt against an email that doesn't match any account."""
    fields = {
        "user_id": user_id,
        "username": username_snapshot,
        "tool_name": event,
        "category": "auth",
        "success": success,
        "exit_code": None,
        "duration_ms": 0,
        "ip_address": ip_address,
        "error_message": None,
    }
    _audit_logger.info("", extra={"audit_fields": fields})

    try:
        db.add(
            AuditLog(
                user_id=user_id,
                username_snapshot=username_snapshot,
                tool_name=event,
                category="auth",
                success=success,
                exit_code=None,
                output_excerpt=None,
                error_message=None,
                duration_ms=0,
                ip_address=ip_address,
            )
        )
        db.commit()
    except Exception:
        db.rollback()
