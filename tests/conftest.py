import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app import app
from backend.auth.dependencies import require_api_user, require_page_user
from backend.db.base import Base
from backend.db.models import Role, User
from backend.db.session import get_db
from backend.security import hash_password


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
    session = TestingSessionLocal()
    try:
        yield session
    finally:
        session.close()
        engine.dispose()


@pytest.fixture()
def make_user(db_session):
    def _make(email, role, display_name="Test User", password="password123"):
        user = User(
            email=email,
            display_name=display_name,
            password_hash=hash_password(password),
            role=role,
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
        return user

    return _make


@pytest.fixture()
def employee_user(make_user):
    return make_user("employee@example.com", Role.EMPLOYEE, display_name="Employee")


@pytest.fixture()
def technician_user(make_user):
    return make_user("tech@example.com", Role.TECHNICIAN, display_name="Technician")


@pytest.fixture()
def client(db_session):
    def _override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _authed(client_fixture, user):
    app.dependency_overrides[require_api_user] = lambda: user
    app.dependency_overrides[require_page_user] = lambda: user
    yield client_fixture
    app.dependency_overrides.pop(require_api_user, None)
    app.dependency_overrides.pop(require_page_user, None)


@pytest.fixture()
def employee_client(client, employee_user):
    yield from _authed(client, employee_user)


@pytest.fixture()
def technician_client(client, technician_user):
    yield from _authed(client, technician_user)
