"""Integration tests for the /api/auth routes."""

from src.repository import users as repository_users
from src.services import auth as auth_service
from tests.conftest import make_user

SIGNUP_PAYLOAD = {
    "username": "newcomer",
    "email": "newcomer@example.com",
    "password": "secret123",
}


def login(client, email="murad@example.com", password="secret123"):
    return client.post("/api/auth/login", data={"username": email, "password": password})


class TestSignup:
    def test_returns_201_and_the_user_without_the_password(self, client):
        response = client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == SIGNUP_PAYLOAD["email"]
        assert data["role"] == "user"
        assert data["confirmed"] is False
        assert "password" not in data

    def test_duplicate_email_answers_409(self, client):
        client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)

        response = client.post("/api/auth/signup", json=SIGNUP_PAYLOAD)

        assert response.status_code == 409

    def test_invalid_payload_answers_422(self, client):
        response = client.post(
            "/api/auth/signup",
            json={"username": "x", "email": "not-an-email", "password": "123"},
        )

        assert response.status_code == 422


class TestLogin:
    def test_unknown_email_answers_401(self, client):
        assert login(client).status_code == 401

    def test_wrong_password_answers_401(self, client, user):
        assert login(client, password="wrong").status_code == 401

    def test_unconfirmed_email_answers_401(self, client, session):
        make_user(session, email="fresh@example.com", confirmed=False)

        response = login(client, email="fresh@example.com")

        assert response.status_code == 401
        assert response.json()["detail"] == "Email not confirmed"

    def test_success_returns_a_token_pair(self, client, user):
        response = login(client)

        assert response.status_code == 200
        data = response.json()
        assert data["token_type"] == "bearer"
        assert data["access_token"] != data["refresh_token"]


class TestEmailVerification:
    def test_confirmation_link_confirms_the_account(self, client, session):
        make_user(session, email="fresh@example.com", confirmed=False)
        token = auth_service.create_email_token("fresh@example.com")

        response = client.get(f"/api/auth/confirmed_email/{token}")

        assert response.status_code == 200
        assert response.json()["message"] == "Email confirmed"
        assert login(client, email="fresh@example.com").status_code == 200

    def test_second_visit_reports_already_confirmed(self, client, user):
        token = auth_service.create_email_token(user.email)

        response = client.get(f"/api/auth/confirmed_email/{token}")

        assert response.json()["message"] == "Your email is already confirmed"

    def test_garbage_token_answers_422(self, client):
        assert client.get("/api/auth/confirmed_email/garbage").status_code == 422

    def test_request_email_is_neutral_for_unknown_addresses(self, client):
        response = client.post(
            "/api/auth/request_email", json={"email": "nobody@example.com"}
        )

        assert response.status_code == 200


class TestRefreshToken:
    def test_refresh_rotates_the_pair(self, client, user):
        tokens = login(client).json()

        response = client.post(
            "/api/auth/refresh_token",
            headers={"Authorization": f"Bearer {tokens['refresh_token']}"},
        )

        assert response.status_code == 200
        assert response.json()["refresh_token"] != tokens["refresh_token"]

    def test_an_old_refresh_token_is_rejected_after_rotation(self, client, user):
        old = login(client).json()["refresh_token"]
        client.post(
            "/api/auth/refresh_token", headers={"Authorization": f"Bearer {old}"}
        )

        response = client.post(
            "/api/auth/refresh_token", headers={"Authorization": f"Bearer {old}"}
        )

        assert response.status_code == 401

    def test_an_access_token_cannot_refresh(self, client, user):
        access = login(client).json()["access_token"]

        response = client.post(
            "/api/auth/refresh_token", headers={"Authorization": f"Bearer {access}"}
        )

        assert response.status_code == 401


class TestPasswordReset:
    def test_forgot_password_is_neutral_for_unknown_addresses(self, client):
        response = client.post(
            "/api/auth/forgot_password", json={"email": "nobody@example.com"}
        )

        assert response.status_code == 200

    def test_reset_changes_the_password_and_signs_sessions_out(
        self, client, session, user
    ):
        refresh = login(client).json()["refresh_token"]
        token = auth_service.create_email_token(user.email, scope="password_reset")

        response = client.post(
            f"/api/auth/reset_password/{token}", json={"password": "brand-new-pass"}
        )

        assert response.status_code == 200
        assert login(client).status_code == 401
        assert login(client, password="brand-new-pass").status_code == 200
        rotated = client.post(
            "/api/auth/refresh_token", headers={"Authorization": f"Bearer {refresh}"}
        )
        assert rotated.status_code == 401

    def test_a_verification_token_cannot_reset_the_password(self, client, user):
        token = auth_service.create_email_token(user.email)

        response = client.post(
            f"/api/auth/reset_password/{token}", json={"password": "brand-new-pass"}
        )

        assert response.status_code == 422
