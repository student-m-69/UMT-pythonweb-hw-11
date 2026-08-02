"""HTTP routes for registration, login, token refresh, email verification
and password reset."""

from typing import Annotated

from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    HTTPException,
    Request,
    status,
)
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer, OAuth2PasswordRequestForm

from src.database.db import DbSession
from src.repository import users as repository_users
from src.schemas import (
    RequestEmail,
    ResetPassword,
    TokenResponse,
    UserCreate,
    UserResponse,
)
from src.services import auth as auth_service
from src.services.email import send_password_reset_email, send_verification_email

router = APIRouter(prefix="/auth", tags=["auth"])
refresh_scheme = HTTPBearer()


def _issue_token_pair(db, user) -> TokenResponse:
    """Create a new access/refresh pair and remember the refresh token.

    Storing the refresh token on the user row makes it single-use: issuing a
    new pair (or resetting the password) invalidates every older one.
    """
    access_token = auth_service.create_access_token(user.email)
    refresh_token = auth_service.create_refresh_token(user.email)
    repository_users.update_refresh_token(db, user, refresh_token)
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


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
    """Create the account and email a verification link in the background.

    Args:
        body: The registration payload (username, email, password).
        background_tasks: FastAPI queue the email is sent through.
        request: Used to build the absolute confirmation link.
        db: The request-scoped database session.

    Returns:
        The created user.

    Raises:
        HTTPException: 409 when the email is already registered.
    """
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


@router.post("/login", response_model=TokenResponse, summary="Obtain a token pair")
def login(body: Annotated[OAuth2PasswordRequestForm, Depends()], db: DbSession):
    """Exchange email + password for an access/refresh token pair.

    The form field is called ``username`` per the OAuth2 spec, but it carries
    the email. A wrong email and a wrong password produce the same 401 on
    purpose, so the endpoint does not leak which accounts exist.

    Args:
        body: The OAuth2 form (``username`` = email, ``password``).
        db: The request-scoped database session.

    Returns:
        The token pair.

    Raises:
        HTTPException: 401 on bad credentials or an unconfirmed email.
    """
    user = repository_users.get_user_by_email(db, body.username)
    if user is None or not auth_service.verify_password(body.password, user.password):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )
    if not user.confirmed:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Email not confirmed")

    return _issue_token_pair(db, user)


@router.post(
    "/refresh_token", response_model=TokenResponse, summary="Refresh the token pair"
)
def refresh_token(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(refresh_scheme)],
    db: DbSession,
):
    """Exchange a valid refresh token for a brand-new token pair.

    The presented token must be exactly the one stored at the last login or
    refresh. A mismatch means the token was already rotated away (possibly
    stolen), so the stored token is revoked and the session ends.

    Args:
        credentials: The ``Authorization: Bearer <refresh_token>`` header.
        db: The request-scoped database session.

    Returns:
        The new token pair.

    Raises:
        HTTPException: 401 when the token is invalid, expired or rotated.
    """
    token = credentials.credentials
    email = auth_service.get_email_from_refresh_token(token)
    user = repository_users.get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    if user.refresh_token != token:
        repository_users.update_refresh_token(db, user, None)
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token")

    return _issue_token_pair(db, user)


@router.get("/confirmed_email/{token}", summary="Confirm the email address")
def confirmed_email(token: str, db: DbSession):
    """Land the link from the verification email.

    Args:
        token: The ``email_token``-scoped JWT from the link.
        db: The request-scoped database session.

    Returns:
        A message describing what happened.

    Raises:
        HTTPException: 422 on a bad token, 400 when the account vanished.
    """
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

    The response is the same whether the account exists or not, again to
    avoid leaking which emails are registered.

    Args:
        body: The payload naming the email.
        background_tasks: FastAPI queue the email is sent through.
        request: Used to build the absolute confirmation link.
        db: The request-scoped database session.

    Returns:
        The same neutral message in every case.
    """
    user = repository_users.get_user_by_email(db, body.email)
    if user and not user.confirmed:
        background_tasks.add_task(
            send_verification_email, user.email, user.username, str(request.base_url)
        )
    return {"message": "Check your email for the confirmation link"}


@router.post("/forgot_password", summary="Request a password-reset email")
def forgot_password(
    body: RequestEmail,
    background_tasks: BackgroundTasks,
    request: Request,
    db: DbSession,
):
    """Queue the password-reset email.

    As with :func:`request_email`, the response never reveals whether the
    address is registered.

    Args:
        body: The payload naming the email.
        background_tasks: FastAPI queue the email is sent through.
        request: Used to build the absolute reset link.
        db: The request-scoped database session.

    Returns:
        The same neutral message in every case.
    """
    user = repository_users.get_user_by_email(db, body.email)
    if user:
        background_tasks.add_task(
            send_password_reset_email, user.email, user.username, str(request.base_url)
        )
    return {"message": "Check your email for the password reset link"}


@router.post("/reset_password/{token}", summary="Set a new password")
def reset_password(token: str, body: ResetPassword, db: DbSession):
    """Complete the reset started by :func:`forgot_password`.

    Setting the new password also revokes the stored refresh token, so every
    existing session is signed out.

    Args:
        token: The ``email_token``-scoped JWT from the reset email.
        body: The payload with the new password.
        db: The request-scoped database session.

    Returns:
        A confirmation message.

    Raises:
        HTTPException: 422 on a bad token, 400 when the account vanished.
    """
    email = auth_service.get_email_from_token(token, scope="password_reset")
    user = repository_users.get_user_by_email(db, email)
    if user is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail="Password reset error")

    repository_users.update_password(
        db, user, auth_service.hash_password(body.password)
    )
    return {"message": "Password updated, please log in again"}
