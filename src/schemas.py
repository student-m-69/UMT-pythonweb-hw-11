"""Pydantic schemas used for request validation and response serialisation.

Validation lives in the annotated types below, so the create and update
schemas share exactly the same rules without repeating them.
"""

from datetime import date, datetime
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, EmailStr, Field

# Digits with the usual separators, e.g. +380 (44) 123-45-67
PHONE_PATTERN = r"^\+?[\d\s\-()]{7,30}$"


def _clean_name(value: str) -> str:
    cleaned = value.strip()
    if not cleaned:
        raise ValueError("must not be blank")
    return cleaned


def _past_date(value: date) -> date:
    if value > date.today():
        raise ValueError("birthday cannot be in the future")
    if value.year < 1900:
        raise ValueError("birthday must be after 1900")
    return value


FirstName = Annotated[
    str, Field(min_length=1, max_length=50, examples=["Ivan"]), AfterValidator(_clean_name)
]
LastName = Annotated[
    str, Field(min_length=1, max_length=50, examples=["Petrenko"]), AfterValidator(_clean_name)
]
Phone = Annotated[
    str, Field(pattern=PHONE_PATTERN, max_length=30, examples=["+380441234567"])
]
Birthday = Annotated[date, Field(examples=["1990-05-17"]), AfterValidator(_past_date)]
AdditionalData = Annotated[str | None, Field(max_length=500, examples=["Met at PyCon"])]


class ContactBase(BaseModel):
    first_name: FirstName
    last_name: LastName
    email: EmailStr
    phone: Phone
    birthday: Birthday
    additional_data: AdditionalData = None


class ContactCreate(ContactBase):
    """Payload for creating a contact: all required fields must be present."""


class ContactUpdate(BaseModel):
    """Payload for updating a contact: every field is optional.

    Only the fields actually sent are applied, so a partial update is enough.
    """

    first_name: FirstName | None = None
    last_name: LastName | None = None
    email: EmailStr | None = None
    phone: Phone | None = None
    birthday: Birthday | None = None
    additional_data: AdditionalData = None


class ContactResponse(ContactBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: datetime
    updated_at: datetime


class UserCreate(BaseModel):
    """Payload for registering a new user."""

    username: Annotated[str, Field(min_length=1, max_length=50, examples=["murad"])]
    email: EmailStr
    # bcrypt reads at most 72 bytes, so longer passwords are rejected upfront.
    password: Annotated[str, Field(min_length=6, max_length=72, examples=["secret123"])]


class UserResponse(BaseModel):
    """Public view of an account; never carries the password hash."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    email: EmailStr
    avatar: str | None
    confirmed: bool
    role: str
    created_at: datetime


class TokenResponse(BaseModel):
    """The token pair issued by login and by the refresh endpoint."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RequestEmail(BaseModel):
    """Payload naming the address for a verification or password-reset email."""

    email: EmailStr


class ResetPassword(BaseModel):
    """Payload carrying the new password for the reset flow."""

    # Same bounds as at registration: bcrypt reads at most 72 bytes.
    password: Annotated[str, Field(min_length=6, max_length=72, examples=["newsecret123"])]
