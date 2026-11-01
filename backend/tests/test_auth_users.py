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


class TestImpersonation:
    """TEMPORARY hackathon demo aid: admin view-as-allowlisted-user."""

    def _register(self, client, username):
        response = client.post(
            "/api/auth/register",
            json={"username": username, "password": "correct-horse-8"},
        )
        assert response.status_code == 201
        return response.json()

    def test_admin_can_impersonate_allowlisted_user(self, store, monkeypatch):
        monkeypatch.setattr(main.config.auth, "demo_view_users", "alice,bob")
        client = _client()
        admin_token = self._register(client, "boss")["token"]
        self._register(client, "alice")
        response = client.post(
            "/api/auth/impersonate",
            json={"username": "alice"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["username"] == "alice"
        assert body["impersonated_from"] == "boss"
        assert body["token"]
        me = client.get(
            "/api/auth/verify", headers={"Authorization": f"Bearer {body['token']}"}
        ).json()
        assert me["username"] == "alice"
        assert me["is_admin"] is False

    def test_impersonation_is_audit_logged(self, store, monkeypatch):
        monkeypatch.setattr(main.config.auth, "demo_view_users", "alice")
        client = _client()
        admin_token = self._register(client, "boss")["token"]
        self._register(client, "alice")
        client.post(
            "/api/auth/impersonate",
            json={"username": "alice"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        events = [
            e
            for e in main.get_audit_log().read()
            if e["event"] == "impersonation_started"
        ]
        assert len(events) == 1
        assert events[0]["actor"] == "boss"
        assert events[0]["actor_role"] == "admin"

    def test_non_admin_cannot_impersonate(self, store, monkeypatch):
        monkeypatch.setattr(main.config.auth, "demo_view_users", "alice,bob")
        client = _client()
        self._register(client, "boss")
        bob_token = self._register(client, "bob")["token"]
        self._register(client, "alice")
        response = client.post(
            "/api/auth/impersonate",
            json={"username": "alice"},
            headers={"Authorization": f"Bearer {bob_token}"},
        )
        assert response.status_code == 403

    def test_new_enrollee_outside_allowlist_rejected(self, store, monkeypatch):
        monkeypatch.setattr(main.config.auth, "demo_view_users", "alice")
        client = _client()
        admin_token = self._register(client, "boss")["token"]
        self._register(client, "alice")
        self._register(client, "mallory")
        response = client.post(
            "/api/auth/impersonate",
            json={"username": "mallory"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 403

    def test_unknown_username_returns_404(self, store, monkeypatch):
        monkeypatch.setattr(main.config.auth, "demo_view_users", "alice,ghost")
        client = _client()
        admin_token = self._register(client, "boss")["token"]
        response = client.post(
            "/api/auth/impersonate",
            json={"username": "ghost"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 404

    def test_admin_cannot_impersonate_admin(self, store, monkeypatch):
        monkeypatch.setattr(main.config.auth, "demo_view_users", "boss,alice")
        client = _client()
        admin_token = self._register(client, "boss")["token"]
        self._register(client, "alice")
        response = client.post(
            "/api/auth/impersonate",
            json={"username": "boss"},
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 403

    def test_demo_users_lists_only_existing_allowlisted(self, store, monkeypatch):
        monkeypatch.setattr(main.config.auth, "demo_view_users", "alice,bob,ghost")
        client = _client()
        admin_token = self._register(client, "boss")["token"]
        self._register(client, "alice")
        self._register(client, "mallory")
        response = client.get(
            "/api/auth/demo-users",
            headers={"Authorization": f"Bearer {admin_token}"},
        )
        assert response.status_code == 200
        assert response.json()["users"] == [{"username": "alice"}]


class TestChangePassword:
    def _register(self, client, username):
        response = client.post(
            "/api/auth/register",
            json={"username": username, "password": "correct-horse-8"},
        )
        assert response.status_code == 201
        return response.json()

    def _change(self, client, token, current_password, new_password):
        return client.post(
            "/api/auth/change-password",
            json={"current_password": current_password, "new_password": new_password},
            headers={"Authorization": f"Bearer {token}"},
        )

    def _login(self, client, username, password):
        return client.post(
            "/api/auth/login", json={"username": username, "password": password}
        )

    def test_change_then_new_password_works(self, store):
        client = _client()
        token = self._register(client, "alice")["token"]
        response = self._change(client, token, "correct-horse-8", "fresh-horse-9x")
        assert response.status_code == 200
        assert response.json()["username"] == "alice"
        assert self._login(client, "alice", "correct-horse-8").status_code == 401
        assert self._login(client, "alice", "fresh-horse-9x").status_code == 200

    def test_wrong_current_password_rejected(self, store):
        client = _client()
        token = self._register(client, "alice")["token"]
        response = self._change(client, token, "wrong-horse-0", "fresh-horse-9x")
        assert response.status_code == 401
        assert self._login(client, "alice", "correct-horse-8").status_code == 200

    def test_weak_new_password_rejected(self, store):
        client = _client()
        token = self._register(client, "alice")["token"]
        assert self._change(client, token, "correct-horse-8", "short").status_code == 400

    def test_unauthenticated_rejected(self, store):
        client = _client()
        self._register(client, "alice")
        response = client.post(
            "/api/auth/change-password",
            json={"current_password": "correct-horse-8", "new_password": "fresh-horse-9x"},
        )
        assert response.status_code == 401

    def test_only_own_password_changes(self, store):
        client = _client()
        self._register(client, "boss")
        bob_token = self._register(client, "bob")["token"]
        response = self._change(client, bob_token, "correct-horse-8", "bob-fresh-1z")
        assert response.json()["username"] == "bob"
        assert self._login(client, "boss", "correct-horse-8").status_code == 200

    def test_no_user_store_returns_404(self, store, monkeypatch):
        client = _client()
        token = self._register(client, "alice")["token"]
        monkeypatch.setattr(main, "get_user_store", lambda: None)
        response = self._change(client, token, "correct-horse-8", "fresh-horse-9x")
        assert response.status_code == 404


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
        assert body == {
            "authenticated": False,
            "username": None,
            "auth_required": True,
            "is_admin": False,
        }

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


class TestFirstAdminRace:
    def test_concurrent_first_registrations_yield_single_admin(self, store, monkeypatch):
        """N threads racing on one empty shared store → exactly one admin.

        Mirrors production: UserStore holds a single connection shared
        across FastAPI threadpool workers (check_same_thread=False).
        """
        import threading

        # Instant hashing aligns every thread at the count+insert critical
        # section. Real bcrypt staggers arrivals by hundreds of ms, so the
        # unlocked read-modify-write window rarely collides and the race
        # hides; hash speed is irrelevant to the atomicity under test.
        monkeypatch.setattr(
            "services.user_store.bcrypt.hashpw", lambda pw, salt: b"x" * 60
        )

        count = 16
        barrier = threading.Barrier(count)
        errors = []

        def attempt(i):
            try:
                barrier.wait(timeout=30)
                store.register(f"racer{i}", "correct-horse-8")
            except Exception as exc:  # record, don't swallow in thread
                errors.append(exc)

        threads = [threading.Thread(target=attempt, args=(i,)) for i in range(count)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert not any(thread.is_alive() for thread in threads)
        assert errors == []
        users = store.list_users()
        assert len(users) == count
        assert sum(1 for user in users if user["is_admin"]) == 1

    def test_concurrent_duplicate_username_registers_once(self, store):
        """Same username raced from two threads → one success, one 409."""
        import threading

        from services.user_store import RegistrationError

        barrier = threading.Barrier(2)
        outcomes = []

        def attempt():
            try:
                barrier.wait(timeout=30)
                store.register("dupe", "correct-horse-8")
                outcomes.append("registered")
            except RegistrationError as exc:
                outcomes.append(exc.code)

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=60)

        assert sorted(outcomes) == ["registered", "username_taken"]


class TestAuthBypassIsolation:
    def test_bypass_independent_of_populated_decoy_db(self, tmp_path):
        """A populated users DB elsewhere must not enable auth for tests.

        Simulates a developer's pre-populated backend/users.db: users exist
        in another store file, yet the app's per-test store stays empty so
        protected endpoints keep the auth bypass (200, not 401).
        """
        from pathlib import Path

        decoy = UserStore(str(tmp_path / "populated-users.db"))
        try:
            decoy.register("localdev", "correct-horse-8")
            decoy.register("localdev2", "correct-horse-8")
        finally:
            decoy.close()

        active_db = Path(main.config.auth.users_db_path)
        assert active_db.parent == tmp_path
        assert active_db != Path(main.__file__).parent / "users.db"
        assert main.get_user_store().count_users() == 0
        assert main._auth_required() is False
        assert _client().get("/config/providers").status_code == 200
