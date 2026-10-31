"""In-app registration and multi-user auth tests via FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient

import main
from services.user_store import UserStore


@pytest.fixture()
def store(tmp_path, monkeypatch):
    """Isolated user store; legacy single-user auth stays disabled."""
    monkeypatch.setattr(main, "auth_service", None)
    isolated = UserStore(str(tmp_path / "test-users.db"))
    monkeypatch.setattr(main, "user_store", isolated)
    yield isolated
    isolated.close()


def _client():
    return TestClient(main.app)


class TestRegistration:
    def test_first_user_becomes_admin(self, store):
        response = _client().post(
            "/api/auth/register",
            json={"username": "alice", "password": "correct-horse-8"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["username"] == "alice"
        assert body["is_admin"] is True
        assert body["token"]

    def test_second_user_is_not_admin(self, store):
        client = _client()
        client.post("/api/auth/register", json={"username": "alice", "password": "correct-horse-8"})
        body = client.post(
            "/api/auth/register", json={"username": "bob", "password": "correct-horse-8"}
        ).json()
        assert body["is_admin"] is False

    def test_duplicate_username_conflicts(self, store):
        client = _client()
        client.post("/api/auth/register", json={"username": "alice", "password": "correct-horse-8"})
        response = client.post(
            "/api/auth/register", json={"username": "alice", "password": "another-pass-9"}
        )
        assert response.status_code == 409

    def test_weak_password_rejected(self, store):
        response = _client().post(
            "/api/auth/register", json={"username": "alice", "password": "short"}
        )
        assert response.status_code == 400

    def test_bad_username_rejected(self, store):
        response = _client().post(
            "/api/auth/register", json={"username": "a!", "password": "correct-horse-8"}
        )
        assert response.status_code == 400

    def test_registration_disabled_returns_403(self, store, monkeypatch):
        monkeypatch.setattr(main.config.auth, "allow_registration", False)
        response = _client().post(
            "/api/auth/register", json={"username": "alice", "password": "correct-horse-8"}
        )
        assert response.status_code == 403


class TestUserLogin:
    def test_registered_user_can_log_in(self, store):
        client = _client()
        client.post("/api/auth/register", json={"username": "alice", "password": "correct-horse-8"})
        response = client.post(
            "/api/auth/login", json={"username": "alice", "password": "correct-horse-8"}
        )
        assert response.status_code == 200
        assert response.json()["username"] == "alice"

    def test_wrong_password_rejected(self, store):
        client = _client()
        client.post("/api/auth/register", json={"username": "alice", "password": "correct-horse-8"})
        response = client.post(
            "/api/auth/login", json={"username": "alice", "password": "wrong-password"}
        )
        assert response.status_code == 401

    def test_auth_required_once_users_exist(self, store):
        client = _client()
        client.post("/api/auth/register", json={"username": "alice", "password": "correct-horse-8"})
        body = client.get("/api/auth/verify").json()
        assert body == {"authenticated": False, "username": None, "auth_required": True}

    def test_legacy_single_user_still_works(self, tmp_path, monkeypatch):
        """A configured AUTH_PASSWORD_HASH keeps working alongside the store."""
        from services.auth_service import AuthService
        import bcrypt

        secret = "test-secret-for-legacy-login"
        monkeypatch.setattr(main, "auth_service", AuthService(
            username="admin",
            password_hash=bcrypt.hashpw(b"legacy-pass-1", bcrypt.gensalt()).decode(),
            jwt_secret=secret,
            jwt_expiry_hours=8,
        ))
        isolated = UserStore(str(tmp_path / "legacy-users.db"))
        monkeypatch.setattr(main, "user_store", isolated)
        try:
            response = _client().post(
                "/api/auth/login", json={"username": "admin", "password": "legacy-pass-1"}
            )
            assert response.status_code == 200
        finally:
            isolated.close()


class TestUserListing:
    def _admin_token(self):
        client = _client()
        client.post("/api/auth/register", json={"username": "root", "password": "correct-horse-8"})
        client.post("/api/auth/register", json={"username": "alice", "password": "correct-horse-8"})
        return client.post(
            "/api/auth/login", json={"username": "root", "password": "correct-horse-8"}
        ).json()["token"]

    def test_admin_can_list_users(self, store):
        token = self._admin_token()
        response = _client().get(
            "/api/auth/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 200
        usernames = [u["username"] for u in response.json()["users"]]
        assert usernames == ["root", "alice"]

    def test_non_admin_cannot_list_users(self, store):
        client = _client()
        client.post("/api/auth/register", json={"username": "root", "password": "correct-horse-8"})
        token = client.post(
            "/api/auth/register", json={"username": "bob", "password": "correct-horse-8"}
        ).json()["token"]
        response = client.get(
            "/api/auth/users", headers={"Authorization": f"Bearer {token}"}
        )
        assert response.status_code == 403

    def test_anonymous_cannot_list_users(self, store):
        _client().post("/api/auth/register", json={"username": "root", "password": "correct-horse-8"})
        assert _client().get("/api/auth/users").status_code == 401
