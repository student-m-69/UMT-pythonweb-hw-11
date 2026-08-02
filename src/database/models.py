"""SQLAlchemy models: :class:`User`, :class:`Contact` and the :class:`Role` enum."""

import enum
from datetime import date, datetime

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Declarative base shared by every model."""


class Role(str, enum.Enum):
    """Access roles. Everyone registers as ``user``; ``admin`` is granted by hand."""

    user = "user"
    admin = "admin"


class User(Base):
    """A registered account that owns contacts.

    The ``password`` column always holds a bcrypt hash, never the plain
    password, and ``refresh_token`` holds the currently valid refresh token
    so that a stolen old token cannot mint new access tokens.
    """

    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(50), nullable=False)
    email: Mapped[str] = mapped_column(
        String(150), nullable=False, unique=True, index=True
    )
    # bcrypt hash, never the plain password.
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    avatar: Mapped[str | None] = mapped_column(String(255), nullable=True)
    confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    role: Mapped[Role] = mapped_column(
        Enum(Role, name="role"), default=Role.user, server_default="user", nullable=False
    )
    refresh_token: Mapped[str | None] = mapped_column(String(500), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    contacts: Mapped[list["Contact"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<User id={self.id} email={self.email}>"


class Contact(Base):
    """One entry of a user's personal phone book."""

    __tablename__ = "contacts"
    # An email may repeat across users, but stays unique within one user's book.
    __table_args__ = (
        UniqueConstraint("user_id", "email", name="uq_contacts_user_email"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    first_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    last_name: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    email: Mapped[str] = mapped_column(String(150), nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(30), nullable=False)
    birthday: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    # The only optional field of the contact.
    additional_data: Mapped[str | None] = mapped_column(String(500), nullable=True)

    user_id: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user: Mapped[User] = relationship(back_populates="contacts")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    def __repr__(self) -> str:
        return f"<Contact id={self.id} {self.first_name} {self.last_name}>"
