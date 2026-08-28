from datetime import timedelta

from sqlalchemy.orm import Session as DbSession

from backend.config import get_settings
from backend.db.models import Session as SessionModel, User
from backend.security import generate_session_token, hash_token, verify_password
from backend.timeutil import utcnow

settings = get_settings()


def authenticate_user(db: DbSession, email: str, password: str) -> User | None:
    user = db.query(User).filter(User.email == email.strip().lower(), User.is_active.is_(True)).first()
    if user is None or not verify_password(password, user.password_hash):
        return None
    return user


def create_session(db: DbSession, user: User, *, ip_address: str | None, user_agent: str | None) -> str:
    token = generate_session_token()
    now = utcnow()
    session = SessionModel(
        token_hash=hash_token(token),
        user_id=user.id,
        created_at=now,
        expires_at=now + timedelta(hours=settings.session_ttl_hours),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    user.last_login_at = now
    db.add(session)
    db.commit()
    return token


def get_session_user(db: DbSession, token: str) -> User | None:
    if not token:
        return None
    token_hash = hash_token(token)
    now = utcnow()
    session = (
        db.query(SessionModel)
        .filter(SessionModel.token_hash == token_hash, SessionModel.revoked_at.is_(None))
        .first()
    )
    if session is None or session.expires_at < now:
        return None
    user = db.query(User).filter(User.id == session.user_id, User.is_active.is_(True)).first()
    return user


def revoke_session(db: DbSession, token: str) -> None:
    token_hash = hash_token(token)
    session = db.query(SessionModel).filter(SessionModel.token_hash == token_hash).first()
    if session is not None:
        session.revoked_at = utcnow()
        db.commit()


def revoke_other_sessions(db: DbSession, user: User, keep_token_hash: str) -> None:
    now = utcnow()
    (
        db.query(SessionModel)
        .filter(
            SessionModel.user_id == user.id,
            SessionModel.token_hash != keep_token_hash,
            SessionModel.revoked_at.is_(None),
        )
        .update({"revoked_at": now})
    )
    db.commit()
