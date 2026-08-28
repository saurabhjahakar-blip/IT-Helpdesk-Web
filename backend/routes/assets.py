from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session as DbSession

from backend.auth.dependencies import require_api_user, require_csrf
from backend.db.models import User
from backend.db.session import get_db
from backend.services.asset_service import capture_snapshot, list_snapshots

router = APIRouter()


@router.post("/snapshot")
def snapshot(
    user: User = Depends(require_api_user),
    db: DbSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    result = capture_snapshot(db, user)
    return {"id": result.id, "captured_at": result.captured_at.isoformat()}


@router.get("/")
def list_all(user: User = Depends(require_api_user), db: DbSession = Depends(get_db)):
    snapshots = list_snapshots(db)
    return [
        {
            "id": s.id,
            "captured_at": s.captured_at.isoformat(),
            "computer_name": s.computer_name,
            "os_name": s.os_name,
            "os_build": s.os_build,
            "cpu_name": s.cpu_name,
            "ram_total_gb": s.ram_total_gb,
            "ram_percent": s.ram_percent,
            "disk_total_gb": s.disk_total_gb,
            "disk_percent": s.disk_percent,
        }
        for s in snapshots
    ]
