"""Integration tests for the /api/contacts routes."""

from datetime import date, timedelta

import pytest

from tests.conftest import auth_headers, make_user

CONTACT = {
    "first_name": "Ivan",
    "last_name": "Petrenko",
    "email": "ivan@example.com",
    "phone": "+380441234567",
    "birthday": "1990-05-17",
}


@pytest.fixture()
def headers(user):
    return auth_headers(user)


def test_every_route_requires_a_token(client):
    assert client.get("/api/contacts").status_code == 401
    assert client.post("/api/contacts", json=CONTACT).status_code == 401
    assert client.get("/api/contacts/1").status_code == 401
    assert client.put("/api/contacts/1", json={}).status_code == 401
    assert client.delete("/api/contacts/1").status_code == 401
    assert client.get("/api/contacts/birthdays").status_code == 401


def test_a_bogus_token_answers_401(client):
    response = client.get(
        "/api/contacts", headers={"Authorization": "Bearer not-a-jwt"}
    )

    assert response.status_code == 401


def test_create_answers_201(client, headers):
    response = client.post("/api/contacts", json=CONTACT, headers=headers)

    assert response.status_code == 201
    data = response.json()
    assert data["email"] == CONTACT["email"]
    assert data["id"] > 0


def test_duplicate_email_in_own_book_answers_409(client, headers):
    client.post("/api/contacts", json=CONTACT, headers=headers)

    response = client.post("/api/contacts", json=CONTACT, headers=headers)

    assert response.status_code == 409


def test_list_and_search(client, headers):
    client.post("/api/contacts", json=CONTACT, headers=headers)
    client.post(
        "/api/contacts",
        json={**CONTACT, "first_name": "Petro", "email": "petro@example.com"},
        headers=headers,
    )

    everyone = client.get("/api/contacts", headers=headers).json()
    filtered = client.get("/api/contacts?first_name=pet", headers=headers).json()

    assert len(everyone) == 2
    assert [c["first_name"] for c in filtered] == ["Petro"]


def test_read_update_delete_cycle(client, headers):
    created = client.post("/api/contacts", json=CONTACT, headers=headers).json()
    contact_id = created["id"]

    got = client.get(f"/api/contacts/{contact_id}", headers=headers)
    assert got.status_code == 200

    updated = client.put(
        f"/api/contacts/{contact_id}", json={"phone": "+380671112233"}, headers=headers
    )
    assert updated.status_code == 200
    assert updated.json()["phone"] == "+380671112233"
    assert updated.json()["first_name"] == CONTACT["first_name"]

    deleted = client.delete(f"/api/contacts/{contact_id}", headers=headers)
    assert deleted.status_code == 204
    assert client.get(f"/api/contacts/{contact_id}", headers=headers).status_code == 404


def test_missing_contact_answers_404(client, headers):
    assert client.get("/api/contacts/999", headers=headers).status_code == 404
    assert client.put("/api/contacts/999", json={}, headers=headers).status_code == 404
    assert client.delete("/api/contacts/999", headers=headers).status_code == 404


def test_users_never_see_each_others_contacts(client, session, headers):
    created = client.post("/api/contacts", json=CONTACT, headers=headers).json()
    other = make_user(session, email="other@example.com", username="other")
    other_headers = auth_headers(other)

    assert client.get("/api/contacts", headers=other_headers).json() == []
    assert (
        client.get(f"/api/contacts/{created['id']}", headers=other_headers).status_code
        == 404
    )
    assert (
        client.delete(f"/api/contacts/{created['id']}", headers=other_headers).status_code
        == 404
    )
    # The same contact email is allowed in another user's book.
    assert (
        client.post("/api/contacts", json=CONTACT, headers=other_headers).status_code
        == 201
    )


def test_birthdays_route_returns_the_window(client, headers):
    soon = (date.today() + timedelta(days=2)).replace(year=1992)
    far = (date.today() + timedelta(days=60)).replace(year=1992)
    client.post(
        "/api/contacts", json={**CONTACT, "birthday": soon.isoformat()}, headers=headers
    )
    client.post(
        "/api/contacts",
        json={**CONTACT, "email": "far@example.com", "birthday": far.isoformat()},
        headers=headers,
    )

    response = client.get("/api/contacts/birthdays", headers=headers)

    assert response.status_code == 200
    assert [c["email"] for c in response.json()] == [CONTACT["email"]]
