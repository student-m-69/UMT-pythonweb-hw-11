"""Shared fixtures: an in-memory database, a fake Redis and ready-made users.

The environment is pinned before anything from ``src`` is imported, so the
suite runs the same with or without a local ``.env`` file.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-not-for-production")
os.environ["CLOUDINARY_NAME"] = ""
os.environ["MAIL_SERVER"] = ""

import fakeredis
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from main import app
from src.database.db import get_db
from src.database.models import Base, Role, User
from src.services import auth as auth_service
from src.services import cache
from src.services.limiter import limiter

engine = create_engine(
    "sqlite://",
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)
TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)


@pytest.fixture()
def session():
    """A database session against a freshly created schema, per test."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


@pytest.fixture(autouse=True)
def fake_redis(monkeypatch):
    """Point the cache module at fakeredis and start every test cold."""
    client = fakeredis.FakeRedis(decode_responses=True)
    monkeypatch.setattr(cache, "_client", client)
    monkeypatch.setattr(cache, "_warned", False)
    yield client


@pytest.fixture(autouse=True)
def reset_rate_limits():
    """Each test gets an untouched rate-limit budget."""
    limiter.reset()


@pytest.fixture()
def client(session):
    """A TestClient whose requests run against the test database."""

    def override_get_db():
        yield session

    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def make_user(
    session,
    email: str = "murad@example.com",
    username: str = "murad",
    password: str = "secret123",
    confirmed: bool = True,
    role: Role = Role.user,
) -> User:
    """Insert a user directly, bypassing the HTTP layer."""
    user = User(
        username=username,
        email=email,
        password=auth_service.hash_password(password),
        confirmed=confirmed,
        role=role,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


@pytest.fixture()
def user(session) -> User:
    """A confirmed regular user."""
    return make_user(session)


@pytest.fixture()
def admin(session) -> User:
    """A confirmed administrator."""
    return make_user(
        session, email="admin@example.com", username="admin", role=Role.admin
    )


def auth_headers(user: User) -> dict[str, str]:
    """Authorization headers with a fresh access token for ``user``."""
    token = auth_service.create_access_token(user.email)
    return {"Authorization": f"Bearer {token}"}
