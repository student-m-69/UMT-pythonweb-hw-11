"""Password hashing and JWT handling.

Two kinds of tokens are issued, told apart by the ``scope`` claim:

- ``access_token`` — short-lived, sent as ``Authorization: Bearer`` and
  exchanged for the current user by the :func:`get_current_user` dependency;
- ``email_token`` — long-lived, embedded in the verification link that the
  signup email contains.
"""

from datetime import datetime, timedelta, timezone
from typing import Annotated

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer

from src.conf.config import settings
from src.database.db import DbSession
from src.database.models import User
from src.repository import users as repository_users

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")


def hash_password(password: str) -> str:
    """Return a bcrypt hash; the plain password is never stored."""
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    return bcrypt.checkpw(plain_password.encode(), hashed_password.encode())


def _create_token(email: str, scope: str, lifetime: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {"sub": email, "scope": scope, "iat": now, "exp": now + lifetime}
    return jwt.encode(payload, settings.secret_key, algorithm=settings.algorithm)


def create_access_token(email: str) -> str:
    return _create_token(
        email,
        scope="access_token",
        lifetime=timedelta(minutes=settings.access_token_expire_minutes),
    )


def create_email_token(email: str) -> str:
    """Token for the verification link; a week leaves time to open the email."""
    return _create_token(email, scope="email_token", lifetime=timedelta(days=7))


def get_email_from_token(token: str) -> str:
    """Read the email out of a verification token or fail with 422."""
    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.PyJWTError as error:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid token for email verification",
        ) from error

    if payload.get("scope") != "email_token" or not payload.get("sub"):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Invalid token for email verification",
        )
    return payload["sub"]


def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], db: DbSession
) -> User:
    """Resolve the Bearer token into a user; any defect means 401."""
    credentials_exception = HTTPException(
        status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    try:
        payload = jwt.decode(
            token, settings.secret_key, algorithms=[settings.algorithm]
        )
    except jwt.PyJWTError as error:
        raise credentials_exception from error

    if payload.get("scope") != "access_token":
        raise credentials_exception
    email = payload.get("sub")
    if not email:
        raise credentials_exception

    user = repository_users.get_user_by_email(db, email)
    if user is None:
        raise credentials_exception
    return user


# Route signatures use this instead of `user: User = Depends(get_current_user)`.
CurrentUser = Annotated[User, Depends(get_current_user)]
