"""Database access for contacts. Every query goes through SQLAlchemy."""

import calendar
from datetime import date, timedelta

from sqlalchemy import extract, or_, select, tuple_
from sqlalchemy.orm import Session

from src.database.models import Contact
from src.schemas import ContactCreate, ContactUpdate


def get_contacts(
    db: Session,
    skip: int = 0,
    limit: int = 100,
    first_name: str | None = None,
    last_name: str | None = None,
    email: str | None = None,
    search: str | None = None,
) -> list[Contact]:
    """List contacts, optionally narrowed by the search query parameters.

    The named filters are combined with AND; ``search`` matches any of the
    three fields. All matching is case-insensitive and partial.
    """
    stmt = select(Contact)

    if first_name:
        stmt = stmt.where(Contact.first_name.ilike(f"%{first_name}%"))
    if last_name:
        stmt = stmt.where(Contact.last_name.ilike(f"%{last_name}%"))
    if email:
        stmt = stmt.where(Contact.email.ilike(f"%{email}%"))
    if search:
        stmt = stmt.where(
            or_(
                Contact.first_name.ilike(f"%{search}%"),
                Contact.last_name.ilike(f"%{search}%"),
                Contact.email.ilike(f"%{search}%"),
            )
        )

    stmt = stmt.order_by(Contact.id).offset(skip).limit(limit)
    return list(db.execute(stmt).scalars().all())


def get_contact(db: Session, contact_id: int) -> Contact | None:
    return db.get(Contact, contact_id)


def get_contact_by_email(db: Session, email: str) -> Contact | None:
    stmt = select(Contact).where(Contact.email == email)
    return db.execute(stmt).scalars().first()


def get_upcoming_birthdays(db: Session, days: int = 7) -> list[Contact]:
    """Contacts whose birthday falls within the next ``days`` days, today included.

    Matching is done on (month, day) pairs rather than on the stored year, which
    makes the turn of the year work without a special case: a window starting on
    28 December simply contains a few January pairs.
    """
    today = date.today()
    window = [today + timedelta(days=offset) for offset in range(days)]
    month_day = [(day.month, day.day) for day in window]

    # A 29 February birthday has no anniversary in a common year, so let it
    # show up on 28 February instead of disappearing entirely.
    if not calendar.isleap(today.year) and (2, 28) in month_day:
        month_day.append((2, 29))

    stmt = select(Contact).where(
        tuple_(
            extract("month", Contact.birthday),
            extract("day", Contact.birthday),
        ).in_(month_day)
    )
    contacts = list(db.execute(stmt).scalars().all())

    # Sort by how soon the birthday is, which plain (month, day) cannot express
    # once the window wraps into the next year.
    position = {pair: index for index, pair in enumerate(month_day)}
    contacts.sort(key=lambda c: position.get((c.birthday.month, c.birthday.day), len(month_day)))
    return contacts


def create_contact(db: Session, body: ContactCreate) -> Contact:
    contact = Contact(**body.model_dump())
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


def update_contact(db: Session, contact: Contact, body: ContactUpdate) -> Contact:
    # exclude_unset keeps the fields the client did not send untouched.
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(contact, field, value)
    db.commit()
    db.refresh(contact)
    return contact


def remove_contact(db: Session, contact: Contact) -> None:
    db.delete(contact)
    db.commit()
