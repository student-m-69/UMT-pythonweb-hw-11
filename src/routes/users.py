"""HTTP routes for the current user's profile."""

import cloudinary
import cloudinary.uploader
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status

from src.conf.config import settings
from src.database.db import DbSession
from src.database.models import Role
from src.repository import users as repository_users
from src.schemas import UserResponse
from src.services.auth import CurrentUser, RoleAccess
from src.services.limiter import limiter

router = APIRouter(prefix="/users", tags=["users"])

admin_only = RoleAccess([Role.admin])


@router.get("/me", response_model=UserResponse, summary="The authenticated user")
@limiter.limit("10/minute")
def read_me(request: Request, user: CurrentUser):
    """Return the profile of the token's owner.

    Limited to 10 requests per minute per client address; beyond that the
    server answers 429.

    Args:
        request: Required by slowapi, which reads the client address from it.
        user: The authenticated user resolved from the Bearer token.

    Returns:
        The current user's profile.
    """
    return user


@router.patch(
    "/avatar",
    response_model=UserResponse,
    summary="Upload a new avatar (admins only)",
)
def update_avatar(
    user: CurrentUser,
    db: DbSession,
    file: UploadFile = File(...),
    _: None = Depends(admin_only),
):
    """Store the image in Cloudinary and save the delivery URL.

    Only administrators may change their default avatar themselves; a
    regular user gets 403.

    Args:
        user: The authenticated user (must have the ``admin`` role).
        db: The request-scoped database session.
        file: The uploaded image.

    Returns:
        The user with the refreshed avatar URL.

    Raises:
        HTTPException: 403 for non-admins, 503 when Cloudinary credentials
            are not configured.
    """
    if not settings.cloudinary_name:
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Cloudinary is not configured on the server",
        )

    cloudinary.config(
        cloud_name=settings.cloudinary_name,
        api_key=settings.cloudinary_api_key,
        api_secret=settings.cloudinary_api_secret,
        secure=True,
    )
    # One public id per user, so a new upload replaces the previous avatar.
    public_id = f"contacts_api/avatars/{user.id}"
    result = cloudinary.uploader.upload(
        file.file, public_id=public_id, overwrite=True
    )
    url = cloudinary.CloudinaryImage(public_id).build_url(
        width=250, height=250, crop="fill", version=result.get("version")
    )
    return repository_users.update_avatar(db, user.email, url)
