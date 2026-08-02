"""Database access for users.

Mutations that change what other requests may see cached (confirmation,
avatar, password) also evict the user from the Redis cache, so no route can
forget to do it.
"""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import User
from src.schemas import UserCreate
from src.services import cache


def get_user_by_email(db: Session, email: str) -> User | None:
    """Fetch a user by email.

    Args:
        db: The database session.
        email: The exact email to look up.

    Returns:
        The user, or ``None`` when the email is not registered.
    """
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalars().first()


def create_user(db: Session, body: UserCreate, password_hash: str) -> User:
    """Persist a new account.

    Args:
        db: The database session.
        body: The validated registration payload.
        password_hash: The bcrypt hash of the password; the plain password
            never reaches this layer.

    Returns:
        The stored user with its generated id.
    """
    user = User(username=body.username, email=body.email, password=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def confirm_email(db: Session, user: User) -> None:
    """Mark the user's email as verified.

    Args:
        db: The database session.
        user: The user to confirm, freshly loaded from this session.
    """
    user.confirmed = True
    db.commit()
    cache.invalidate_user(user.email)


def update_avatar(db: Session, email: str, url: str) -> User:
    """Store a new avatar URL.

    The row is fetched here rather than taken from the caller because the
    authenticated user may be a detached copy rebuilt from the Redis cache,
    and mutating that copy would never reach the database.

    Args:
        db: The database session.
        email: The email of the user whose avatar changes.
        url: The Cloudinary delivery URL.

    Returns:
        The updated user.
    """
    user = get_user_by_email(db, email)
    user.avatar = url
    db.commit()
    db.refresh(user)
    cache.invalidate_user(user.email)
    return user


def update_password(db: Session, user: User, password_hash: str) -> None:
    """Replace the password hash and revoke the active refresh token.

    Dropping the refresh token means a password reset signs out every
    session that could have been hijacked.

    Args:
        db: The database session.
        user: The user resetting their password.
        password_hash: The bcrypt hash of the new password.
    """
    user.password = password_hash
    user.refresh_token = None
    db.commit()
    cache.invalidate_user(user.email)


def update_refresh_token(db: Session, user: User, token: str | None) -> None:
    """Store the currently valid refresh token (or clear it).

    Only the token stored here is accepted by the refresh endpoint, so an
    old token becomes useless the moment a new pair is issued.

    Args:
        db: The database session.
        user: The user the token belongs to.
        token: The new refresh token, or ``None`` to sign the user out.
    """
    user.refresh_token = token
    db.commit()
