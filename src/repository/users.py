"""Database access for users."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.database.models import User
from src.schemas import UserCreate


def get_user_by_email(db: Session, email: str) -> User | None:
    stmt = select(User).where(User.email == email)
    return db.execute(stmt).scalars().first()


def create_user(db: Session, body: UserCreate, password_hash: str) -> User:
    user = User(username=body.username, email=body.email, password=password_hash)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


def confirm_email(db: Session, user: User) -> None:
    user.confirmed = True
    db.commit()


def update_avatar(db: Session, user: User, url: str) -> User:
    user.avatar = url
    db.commit()
    db.refresh(user)
    return user
