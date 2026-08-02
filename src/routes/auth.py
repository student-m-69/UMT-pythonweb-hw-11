"""HTTP routes for registration, login and email verification."""

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import OAuth2PasswordRequestForm

from src.database.db import DbSession
from src.repository import users as repository_users
from src.schemas import RequestEmail, TokenResponse, UserCreate, UserResponse
from src.services import auth as auth_service
from src.services.email import send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post(
    "/signup",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user",
)
def signup(
    body: UserCreate,
    background_tasks: BackgroundTasks,
    request: Request,
    db: DbSession,
):
    """Create the account and email a verification link in the background."""
    if repository_users.get_user_by_email(db, body.email):
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = repository_users.create_user(
        db, body, password_hash=auth_service.hash_password(body.password)
    )
    background_tasks.add_task(
        send_verification_email, user.email, user.username, str(request.base_url)
    )
    return user


@router.post("/login", response_model=TokenResponse, summary="Obtain an access token")
def login(body: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """Exchange email + password for a JWT.

    The form field is called ``username`` per the OAuth2 spec, but it carries
    the email. A wrong email and a wrong password produce the same 401 on
    purpose, so the endpoint does not leak which accounts exist.
    """
    user = repository_users.get_user_by_email(db, body.username)
    if user is None or not auth_service.verify_password(body.password, user.password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not user.confirmed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Email not confirmed")

    return TokenResponse(access_token=auth_service.create_access_token(user.email))


@router.get("/confirmed_email/{token}", summary="Confirm the email address")
def confirmed_email(token: str, db: DbSession):
    """Land the link from the verification email."""
    email = auth_service.get_email_from_token(token)
    user = repository_users.get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Verification error")

    if user.confirmed:
        return {"message": "Your email is already confirmed"}
    repository_users.confirm_email(db, user)
    return {"message": "Email confirmed"}


@router.post("/request_email", summary="Re-send the verification email")
def request_email(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: DbSession,
):
    """Queue another verification email.

    The response is the same whether the account exists or not, again to avoid
    leaking which emails are registered.
    """
    user = repository_users.get_user_by_email(db, body.email)
    if user and not user.confirmed:
        background_tasks.add_task(
            send_verification_email, user.email, user.username, str(request.base_url)
        )
    return {"message": "Check your email for the confirmation link"}
