"""HTTP routes for contacts."""

from fastapi import APIRouter, HTTPException, Query, status

from src.database.db import DbSession
from src.repository import contacts as repository
from src.schemas import ContactCreate, ContactResponse, ContactUpdate

router = APIRouter(prefix="/contacts", tags=["contacts"])


@router.get(
    "/birthdays",
    response_model=list[ContactResponse],
    summary="Contacts with a birthday in the coming days",
)
def upcoming_birthdays(
    db: DbSession,
    days: int = Query(7, ge=1, le=365, description="Size of the window in days"),
):
    """Return contacts whose birthday falls within the next week, today included.

    Declared before ``/{contact_id}`` on purpose: FastAPI matches routes in
    order, and the other one would swallow "birthdays" and fail to parse it
    as an integer.
    """
    return repository.get_upcoming_birthdays(db, days)


@router.get("", response_model=list[ContactResponse], summary="List contacts")
def list_contacts(
    db: DbSession,
    skip: int = Query(0, ge=0),
    limit: int = Query(100, ge=1, le=1000),
    first_name: str | None = Query(None, description="Partial, case-insensitive match"),
    last_name: str | None = Query(None, description="Partial, case-insensitive match"),
    email: str | None = Query(None, description="Partial, case-insensitive match"),
    search: str | None = Query(None, description="Match any of the three fields above"),
):
    return repository.get_contacts(
        db,
        skip=skip,
        limit=limit,
        first_name=first_name,
        last_name=last_name,
        email=email,
        search=search,
    )


@router.get("/{contact_id}", response_model=ContactResponse, summary="Get one contact")
def read_contact(contact_id: int, db: DbSession):
    contact = repository.get_contact(db, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contact not found")
    return contact


@router.post(
    "",
    response_model=ContactResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a contact",
)
def create_contact(body: ContactCreate, db: DbSession):
    if repository.get_contact_by_email(db, body.email):
        raise HTTPException(
            status.HTTP_409_CONFLICT, detail="A contact with this email already exists"
        )
    return repository.create_contact(db, body)


@router.put("/{contact_id}", response_model=ContactResponse, summary="Update a contact")
def update_contact(contact_id: int, body: ContactUpdate, db: DbSession):
    contact = repository.get_contact(db, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contact not found")

    if body.email and body.email != contact.email:
        if repository.get_contact_by_email(db, body.email):
            raise HTTPException(
                status.HTTP_409_CONFLICT,
                detail="A contact with this email already exists",
            )
    return repository.update_contact(db, contact, body)


@router.delete(
    "/{contact_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a contact",
)
def delete_contact(contact_id: int, db: DbSession):
    contact = repository.get_contact(db, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail="Contact not found")
    repository.remove_contact(db, contact)
