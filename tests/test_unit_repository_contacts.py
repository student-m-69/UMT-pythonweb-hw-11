"""Unit tests for src/repository/contacts.py against an in-memory database."""

from datetime import date, timedelta

import pytest

from src.repository import contacts as repository
from src.schemas import ContactCreate, ContactUpdate
from tests.conftest import make_user


@pytest.fixture()
def owner(session):
    return make_user(session)


@pytest.fixture()
def stranger(session):
    return make_user(session, email="other@example.com", username="other")


def build_contact(**overrides) -> ContactCreate:
    data = {
        "first_name": "Ivan",
        "last_name": "Petrenko",
        "email": "ivan@example.com",
        "phone": "+380441234567",
        "birthday": date(1990, 5, 17),
    }
    data.update(overrides)
    return ContactCreate(**data)


def test_create_contact_belongs_to_user(session, owner):
    contact = repository.create_contact(session, build_contact(), owner)

    assert contact.id is not None
    assert contact.user_id == owner.id
    assert contact.first_name == "Ivan"


def test_get_contacts_returns_only_own(session, owner, stranger):
    repository.create_contact(session, build_contact(), owner)
    repository.create_contact(
        session, build_contact(email="foreign@example.com"), stranger
    )

    found = repository.get_contacts(session, owner)

    assert len(found) == 1
    assert found[0].user_id == owner.id


def test_get_contacts_filters_combine_with_and(session, owner):
    repository.create_contact(session, build_contact(), owner)
    repository.create_contact(
        session,
        build_contact(first_name="Petro", email="petro@example.com"),
        owner,
    )

    assert len(repository.get_contacts(session, owner, first_name="iva")) == 1
    assert len(repository.get_contacts(session, owner, first_name="iva", last_name="zzz")) == 0


def test_get_contacts_search_matches_any_field(session, owner):
    repository.create_contact(session, build_contact(), owner)
    repository.create_contact(
        session,
        build_contact(first_name="Petro", last_name="Kovalenko", email="petro@inbox.eu"),
        owner,
    )

    by_name = repository.get_contacts(session, owner, search="koval")
    by_email = repository.get_contacts(session, owner, search="example.com")

    assert [c.last_name for c in by_name] == ["Kovalenko"]
    assert [c.email for c in by_email] == ["ivan@example.com"]


def test_get_contacts_pagination(session, owner):
    for index in range(5):
        repository.create_contact(
            session, build_contact(email=f"c{index}@example.com"), owner
        )

    page = repository.get_contacts(session, owner, skip=2, limit=2)

    assert [c.email for c in page] == ["c2@example.com", "c3@example.com"]


def test_get_contact_hides_foreign_rows(session, owner, stranger):
    contact = repository.create_contact(session, build_contact(), owner)

    assert repository.get_contact(session, contact.id, owner) is contact
    assert repository.get_contact(session, contact.id, stranger) is None
    assert repository.get_contact(session, 9999, owner) is None


def test_get_contact_by_email_scoped_to_user(session, owner, stranger):
    repository.create_contact(session, build_contact(), owner)

    assert repository.get_contact_by_email(session, "ivan@example.com", owner) is not None
    assert repository.get_contact_by_email(session, "ivan@example.com", stranger) is None


def test_update_contact_applies_only_sent_fields(session, owner):
    contact = repository.create_contact(session, build_contact(), owner)

    updated = repository.update_contact(
        session, contact, ContactUpdate(phone="+380671112233")
    )

    assert updated.phone == "+380671112233"
    assert updated.first_name == "Ivan"


def test_remove_contact_deletes_row(session, owner):
    contact = repository.create_contact(session, build_contact(), owner)

    repository.remove_contact(session, contact)

    assert repository.get_contact(session, contact.id, owner) is None


def test_upcoming_birthdays_window_and_ownership(session, owner, stranger):
    today = date.today()
    in_three_days = today + timedelta(days=3)
    far_away = today + timedelta(days=40)

    repository.create_contact(
        session,
        build_contact(
            email="soon@example.com",
            birthday=in_three_days.replace(year=1992),
        ),
        owner,
    )
    repository.create_contact(
        session,
        build_contact(
            email="later@example.com",
            birthday=far_away.replace(year=1992),
        ),
        owner,
    )
    repository.create_contact(
        session,
        build_contact(
            email="foreign@example.com",
            birthday=in_three_days.replace(year=1992),
        ),
        stranger,
    )

    found = repository.get_upcoming_birthdays(session, owner)

    assert [c.email for c in found] == ["soon@example.com"]


def test_upcoming_birthdays_sorted_by_how_soon(session, owner):
    today = date.today()
    for offset, email in ((5, "later@example.com"), (1, "sooner@example.com")):
        birthday = (today + timedelta(days=offset)).replace(year=1992)
        repository.create_contact(
            session, build_contact(email=email, birthday=birthday), owner
        )

    found = repository.get_upcoming_birthdays(session, owner)

    assert [c.email for c in found] == ["sooner@example.com", "later@example.com"]
