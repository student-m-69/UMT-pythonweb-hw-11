"""Password hashing, JWT handling and role checks.

Three kinds of tokens are issued, told apart by the ``scope`` claim so that
none of them can ever stand in for another:

- ``access_token`` — short-lived, sent as ``Authorization: Bearer`` and
  exchanged for the current user by the :func:`get_current_user` dependency;
- ``refresh_token`` — long-lived, stored on the user row and exchanged for a
  fresh token pair by the refresh endpoint;
- ``email_token`` — embedded in the verification and password-reset links
  that the emails contain.
"""

from datetime import datetime, timedelta, timezone
from uuid import uuid4
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import OAuth2PasswordBearer

from src.conf.config import settings
from src.database.db import DbSession
from src.database.models import Role, User
from src.repository import users as repository_users
from src.services import cache

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """Hash a plain password with bcrypt.

    Args:
        password: The plain-text password from the request.

    Returns:
        The bcrypt hash; the plain password is never stored anywhere.
    """
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Check a plain password against its stored bcrypt hash.

    Args:
        plain_password: The candidate password.
        hashed_password: The bcrypt hash kept in the database.

    Returns:
        ``True`` when the password matches.
    """
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def _create_token(email: str, scope: str, lifetime: timedelta) -> str:
    """Sign a JWT for ``email`` with the given ``scope`` and ``lifetime``.

    The ``jti`` claim makes every token unique even when two are minted
    within the same second, which matters for refresh-token rotation.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": email,
        "scope": scope,
        "iat": now,
        "exp": now + lifetime,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(email: str) -> str:
    """Issue the short-lived token that authorises API requests.

    Args:
        email: The account the token will act for.

    Returns:
        The signed JWT with ``scope: access_token``.
    """
    return _create_token(
        email,
        scope="access_token",
        lifetime=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_refresh_token(email: str) -> str:
    """Issue the long-lived token used to obtain new token pairs.

    Args:
        email: The account the token will act for.

    Returns:
        The signed JWT with ``scope: refresh_token``.
    """
    return _create_token(
        email,
        scope="refresh_token",
        lifetime=timedelta(days=settings.refresh_token_expire_days),
    )


def create_email_token(email: str, scope: str = "email_token") -> str:
    """Issue the token embedded in verification and password-reset links.

    A week leaves enough time to open the email. Verification and reset
    links carry different scopes, so one can never be replayed as the other.

    Args:
        email: The address the link will act on.
        scope: ``email_token`` for verification, ``password_reset`` for
            the reset flow.

    Returns:
        The signed JWT.
    """
    return _create_token(email, scope=scope, lifetime=timedelta(days=7))


def _decode_or_none(token: str) -> dict | None:
    """Decode a JWT, returning ``None`` instead of raising on any defect."""
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
    except jwt.PyJWTError:
        return None


def get_email_from_token(token: str, scope: str = "email_token") -> str:
    """Read the email out of a verification or reset token.

    Args:
        token: The JWT taken from the emailed link.
        scope: The scope the token must carry to be accepted.

    Returns:
        The email stored in the ``sub`` claim.

    Raises:
        HTTPException: 422 when the token is invalid, expired or has the
            wrong scope.
    """
    payload = _decode_or_none(token)
    if payload is None or payload.get("scope") != scope or not payload.get("sub"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid token",
        )
    return payload["sub"]


def get_email_from_refresh_token(token: str) -> str:
    """Read the email out of a refresh token.

    Args:
        token: The JWT presented to the refresh endpoint.

    Returns:
        The email stored in the ``sub`` claim.

    Raises:
        HTTPException: 401 when the token is invalid, expired or has the
            wrong scope.
    """
    payload = _decode_or_none(token)
    if payload is None or payload.get("scope") != "refresh_token" or not payload.get("sub"):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    return payload["sub"]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> User:
    """Resolve the Bearer token into a user; any defect means 401.

    The user is looked up in the Redis cache first, so most requests never
    touch PostgreSQL; on a miss the database copy is loaded and cached for
    the next requests. Whatever mutates an account calls
    :func:`src.services.cache.invalidate_user`, which keeps the cache honest.

    Args:
        token: The Bearer token from the ``Authorization`` header.
        db: The request-scoped database session.

    Returns:
        The authenticated :class:`~src.database.models.User`.

    Raises:
        HTTPException: 401 when the token is missing, expired, has the wrong
            scope or names an account that no longer exists.
    """
    credentials_exception = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    payload = _decode_or_none(token)
    if payload is None or payload.get("scope") != "access_token":
        raise credentials_exception
    email = payload.get("sub")
    if not email:
        raise credentials_exception

    user = cache.get_cached_user(email)
    if user is None:
        user = repository_users.get_user_by_email(db, email)
        if user is None:
            raise credentials_exception
        cache.cache_user(user)
    return user


# Route signatures use this instead of `user: User = Depends(get_current_user)`.
CurrentUser = Annotated[User, Depends(get_current_user)]


class RoleAccess:
    """Dependency that lets only the listed roles through.

    Usage::

        router.patch("/avatar", dependencies=[Depends(RoleAccess([Role.admin]))])

    Raises:
        HTTPException: 403 when the authenticated user's role is not allowed.
    """

    def __init__(self, allowed_roles: list[Role]):
        self.allowed_roles = allowed_roles

    def __call__(self, request: Request, user: CurrentUser) -> User:
        if user.role not in self.allowed_roles:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN, detail="Operation forbidden for your role"
            )
        return user
