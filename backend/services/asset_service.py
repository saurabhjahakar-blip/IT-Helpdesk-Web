from sqlalchemy.orm import Session as DbSession

from backend.db.models import AssetSnapshot, User
from backend.services.system_service import get_system_info

_HISTORY_LIMIT = 50


def capture_snapshot(db: DbSession, user: User) -> AssetSnapshot:
    system = get_system_info()
    snapshot = AssetSnapshot(
        captured_by_user_id=user.id,
        computer_name=system["computer_name"],
        domain=system["domain"],
        os_name=system["os_name"],
        os_subtitle=system["os_subtitle"],
        os_build=system["os_build"],
        cpu_name=system["cpu_name"],
        cpu_subtitle=system["cpu_subtitle"],
        ram_total_gb=system["ram_total"],
        disk_total_gb=system["disk_total"],
        disk_used_gb=system["disk_used"],
        disk_percent=system["disk_percent"],
        ram_percent=system["ram_percent"],
    )
    db.add(snapshot)
    db.commit()
    db.refresh(snapshot)
    return snapshot


def list_snapshots(db: DbSession) -> list[AssetSnapshot]:
    return (
        db.query(AssetSnapshot)
        .order_by(AssetSnapshot.captured_at.desc())
        .limit(_HISTORY_LIMIT)
        .all()
    )
