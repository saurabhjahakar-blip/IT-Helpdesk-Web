from datetime import datetime, timezone


def utcnow() -> datetime:
    """Naive UTC timestamp, matching SQLAlchemy's timezone-naive DateTime columns."""
    return datetime.now(timezone.utc).replace(tzinfo=None)
