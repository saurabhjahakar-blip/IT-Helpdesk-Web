from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session as DbSession

from backend.auth.dependencies import require_api_user
from backend.auth.service import revoke_other_sessions
from backend.config import get_settings
from backend.db.models import User
from backend.db.session import get_db
from backend.security import hash_password, hash_token, verify_password

router = APIRouter()
settings = get_settings()


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=8, max_length=255)
    confirm_password: str = Field(min_length=1)


@router.post("/change-password")
def change_password(
    payload: ChangePasswordRequest,
    request: Request,
    user: User = Depends(require_api_user),
    db: DbSession = Depends(get_db),
):
    if not verify_password(payload.current_password, user.password_hash):
        raise HTTPException(status_code=400, detail="Current password is incorrect")
    if payload.new_password != payload.confirm_password:
        raise HTTPException(status_code=400, detail="New password and confirmation do not match")

    user.password_hash = hash_password(payload.new_password)
    db.commit()

    current_token = request.cookies.get(settings.session_cookie_name, "")
    revoke_other_sessions(db, user, keep_token_hash=hash_token(current_token))

    return {"status": "ok"}
