"""Integration tests for the /api/users routes, the Redis cache and the
utility endpoints."""

import io

from src.conf.config import settings
from src.services import cache
from tests.conftest import auth_headers


class TestMe:
    def test_me_returns_the_profile(self, client, user):
        response = client.get("/api/users/me", headers=auth_headers(user))

        assert response.status_code == 200
        data = response.json()
        assert data["email"] == user.email
        assert data["role"] == "user"
        assert "password" not in data

    def test_me_is_rate_limited(self, client, user):
        headers = auth_headers(user)

        codes = [client.get("/api/users/me", headers=headers).status_code for _ in range(11)]

        assert codes[:10] == [200] * 10
        assert codes[10] == 429


class TestUserCache:
    def test_the_first_request_caches_the_user(self, client, user):
        assert cache.get_cached_user(user.email) is None

        client.get("/api/users/me", headers=auth_headers(user))

        cached = cache.get_cached_user(user.email)
        assert cached is not None
        assert cached.id == user.id

    def test_requests_are_served_from_the_cache(self, client, session, user):
        headers = auth_headers(user)
        client.get("/api/users/me", headers=headers)

        # Change the row behind the cache's back: the response must not
        # notice until the entry is invalidated.
        user.username = "renamed"
        session.commit()

        assert client.get("/api/users/me", headers=headers).json()["username"] == "murad"

        cache.invalidate_user(user.email)
        assert client.get("/api/users/me", headers=headers).json()["username"] == "renamed"

    def test_redis_being_down_falls_back_to_the_database(
        self, client, user, monkeypatch
    ):
        monkeypatch.setattr(cache, "_client", None)
        monkeypatch.setattr(
            settings, "redis_url", "redis://localhost:1/0"
        )  # nothing listens there

        response = client.get("/api/users/me", headers=auth_headers(user))

        assert response.status_code == 200


class TestAvatar:
    def _upload(self, client, headers):
        return client.patch(
            "/api/users/avatar",
            headers=headers,
            files={"file": ("avatar.png", io.BytesIO(b"fake-image"), "image/png")},
        )

    def test_regular_users_get_403(self, client, user):
        response = self._upload(client, auth_headers(user))

        assert response.status_code == 403

    def test_admin_without_cloudinary_gets_503(self, client, admin):
        response = self._upload(client, auth_headers(admin))

        assert response.status_code == 503

    def test_admin_upload_stores_the_cloudinary_url(
        self, client, admin, monkeypatch
    ):
        import cloudinary.uploader

        monkeypatch.setattr(settings, "cloudinary_name", "demo")
        monkeypatch.setattr(settings, "cloudinary_api_key", "key")
        monkeypatch.setattr(settings, "cloudinary_api_secret", "secret")
        monkeypatch.setattr(
            cloudinary.uploader, "upload", lambda *a, **kw: {"version": 42}
        )

        response = self._upload(client, auth_headers(admin))

        assert response.status_code == 200
        assert f"avatars/{admin.id}" in response.json()["avatar"]

    def test_avatar_requires_a_token(self, client):
        response = client.patch("/api/users/avatar")

        assert response.status_code == 401


class TestUtility:
    def test_root_greets(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert "docs" in response.json()["message"]

    def test_healthchecker_reports_healthy(self, client):
        response = client.get("/api/healthchecker")

        assert response.status_code == 200
