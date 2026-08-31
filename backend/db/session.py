from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from backend.config import get_settings

settings = get_settings()

_is_sqlite = settings.database_url.startswith("sqlite")

# SQLAlchemy's QueuePool defaults (pool_size=5, max_overflow=10 -> 15 total
# connections) badly bottleneck this app: every request needs a DB session,
# and load testing confirmed 100 concurrent requests pile up for a slot for
# up to pool_timeout each — server work stalls for minutes even for trivial
# unrelated requests (see loadtest results, 2026-08-31). SQLite in WAL mode
# handles far more concurrent readers than 15; the cap was purely an
# unconfigured default, not a real SQLite limit.
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False} if _is_sqlite else {},
    pool_size=40 if _is_sqlite else 5,
    max_overflow=40 if _is_sqlite else 10,
)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if not _is_sqlite:
        return
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    # Have SQLite wait (rather than immediately raise "database is locked")
    # when a write briefly contends with another connection.
    cursor.execute("PRAGMA busy_timeout=5000")
    cursor.close()


SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
