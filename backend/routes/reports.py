from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session as DbSession

from backend.auth.dependencies import require_api_user, require_csrf
from backend.db.models import User
from backend.db.session import get_db
from backend.services.report_service import generate_report, list_reports, render_report_html

router = APIRouter()


@router.post("/generate")
def generate(
    user: User = Depends(require_api_user),
    db: DbSession = Depends(get_db),
    _csrf: None = Depends(require_csrf),
):
    report = generate_report(db, user)
    return {"id": report.id, "created_at": report.created_at.isoformat(), "computer_name": report.computer_name}


@router.get("/")
def list_own(user: User = Depends(require_api_user), db: DbSession = Depends(get_db)):
    reports = list_reports(db, user)
    return [
        {"id": r.id, "created_at": r.created_at.isoformat(), "computer_name": r.computer_name}
        for r in reports
    ]


@router.get("/{report_id}/download")
def download(report_id: int, user: User = Depends(require_api_user), db: DbSession = Depends(get_db)):
    reports = {r.id: r for r in list_reports(db, user)}
    report = reports.get(report_id)
    if report is None:
        raise HTTPException(status_code=404, detail="Report not found")

    html = render_report_html(report, generated_for=user)
    return Response(
        content=html,
        media_type="text/html",
        headers={"Content-Disposition": f'attachment; filename="support-report-{report.id}.html"'},
    )
