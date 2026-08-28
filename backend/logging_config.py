import json
import logging
from logging.handlers import RotatingFileHandler

from backend.config import get_settings

_configured = False


class _JsonLineFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S"),
            "level": record.levelname,
        }
        payload.update(getattr(record, "audit_fields", {}))
        if not payload.get("message"):
            payload["message"] = record.getMessage()
        return json.dumps(payload)


def configure_logging() -> None:
    global _configured
    if _configured:
        return
    settings = get_settings()
    settings.log_dir.mkdir(parents=True, exist_ok=True)

    audit_logger = logging.getLogger("helpdesk.audit")
    audit_logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(
        settings.log_dir / "audit.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    handler.setFormatter(_JsonLineFormatter())
    audit_logger.addHandler(handler)
    audit_logger.propagate = False

    _configured = True


def get_audit_logger() -> logging.Logger:
    return logging.getLogger("helpdesk.audit")
