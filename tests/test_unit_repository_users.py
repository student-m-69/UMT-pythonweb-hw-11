"""Unit tests for src/repository/users.py against an in-memory database."""

from src.database.models import Role
from src.repository import users as repository
from src.schemas import UserCreate
from src.services import cache
from tests.conftest import make_user


def test_create_user_defaults(session):
    body = UserCreate(
        username="murad", email="murad@example.com", password="secret123"
    )

    user = repository.create_user(session, body, password_hash="hashed")

    assert user.id is not None
    assert user.password == "hashed"
    assert user.confirmed is False
    assert user.role == Role.user
    assert user.refresh_token is None


def test_get_user_by_email(session):
    created = make_user(session)

    assert repository.get_user_by_email(session, created.email) is created
    assert repository.get_user_by_email(session, "nobody@example.com") is None


def test_confirm_email_sets_flag_and_evicts_cache(session):
    user = make_user(session, confirmed=False)
    cache.cache_user(user)

    repository.confirm_email(session, user)

    assert user.confirmed is True
    assert cache.get_cached_user(user.email) is None


def test_update_avatar_fetches_fresh_row(session):
    user = make_user(session)
    cache.cache_user(user)

    updated = repository.update_avatar(
        session, user.email, "https://example.com/a.png"
    )

    assert updated.avatar == "https://example.com/a.png"
    assert cache.get_cached_user(user.email) is None


def test_update_password_revokes_refresh_token(session):
    user = make_user(session)
    repository.update_refresh_token(session, user, "old-refresh-token")
    cache.cache_user(user)

    repository.update_password(session, user, "new-hash")

    assert user.password == "new-hash"
    assert user.refresh_token is None
    assert cache.get_cached_user(user.email) is None


def test_update_refresh_token_stores_and_clears(session):
    user = make_user(session)

    repository.update_refresh_token(session, user, "token-1")
    assert user.refresh_token == "token-1"

    repository.update_refresh_token(session, user, None)
    assert user.refresh_token is None


def test_cache_round_trip_never_stores_secrets(session):
    user = make_user(session, role=Role.admin)

    cache.cache_user(user)
    cached = cache.get_cached_user(user.email)

    assert cached.id == user.id
    assert cached.email == user.email
    assert cached.role == Role.admin
    # The rebuilt copy carries no password hash and no refresh token.
    assert cached.password is None
    assert cached.refresh_token is None
