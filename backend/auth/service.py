from datetime import timedelta

from sqlalchemy.orm import Session as DbSession

from backend.auth.ldap_service import LdapUserInfo, authenticate_ldap
from backend.config import get_settings
from backend.db.models import Role, Session as SessionModel, User
from backend.security import generate_session_token, hash_token, verify_password
from backend.timeutil import utcnow

settings = get_settings()


def _authenticate_local(db: DbSession, email: str, password: str, *, require_source: str | None) -> User | None:
    query = db.query(User).filter(User.email == email, User.is_active.is_(True))
    if require_source is not None:
        query = query.filter(User.auth_source == require_source)
    user = query.first()
    if user is None or not user.password_hash or not verify_password(password, user.password_hash):
        return None
    return user


def _sync_ldap_user(db: DbSession, info: LdapUserInfo) -> User | None:
    role = Role.TECHNICIAN if info.is_technician else Role.EMPLOYEE
    user = db.query(User).filter(User.email == info.email).first()

    if user is None:
        user = User(
            email=info.email,
            display_name=info.display_name,
            password_hash=None,
            auth_source="ldap",
            role=role,
            is_active=True,
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        return user

    if not user.is_active:
        # A local deactivation overrides a successful AD bind — gives IT a
        # way to cut someone off here without needing to touch AD itself.
        return None

    user.display_name = info.display_name
    user.role = role
    user.auth_source = "ldap"
    db.commit()
    return user


def authenticate_user(db: DbSession, email: str, password: str) -> User | None:
    identifier = email.strip().lower()

    if settings.ldap_enabled:
        ldap_info = authenticate_ldap(identifier, password)
        if ldap_info is not None:
            return _sync_ldap_user(db, ldap_info)
        # A failed AD bind only ever falls through to the local break-glass
        # account (auth_source == "local") — regular AD-backed accounts have
        # no usable local password, so this never becomes a bypass.
        return _authenticate_local(db, identifier, password, require_source="local")

    return _authenticate_local(db, identifier, password, require_source=None)


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
