"""LLM profiles + provider catalog tests.

Keys are encrypted at rest and must never appear in any API response,
log line, or audit record — several tests below assert exactly that by
scanning serialized bodies for the raw key.
"""
import json

import pytest
from fastapi.testclient import TestClient

import main
from llm_service import PolicyResponse


SAFE_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::example-bucket/*"],
        }
    ],
}


class _StubPolicyProvider:
    def __init__(self, risk="medium"):
        self.risk = risk

    def generate_policy(self, request_text):
        return [
            PolicyResponse(
                policy=dict(SAFE_POLICY),
                risk=self.risk,
                explanation="stub explanation",
                approver_note="stub approver note",
            )
        ]


@pytest.fixture()
def _as_user(monkeypatch):
    monkeypatch.setattr(main, "auth_service", None)
    monkeypatch.setattr(main, "_is_admin", lambda username: username == "boss")

    def use(username):
        main.app.dependency_overrides[main.get_current_user] = lambda: username

    yield use
    main.app.dependency_overrides.clear()


@pytest.fixture()
def _stub_llm(monkeypatch):
    """Stub LLM that also captures the api_key it was constructed with."""
    captured = {}

    def fake_get_llm_provider(provider_type=None, model=None, api_key=None):
        captured["api_key"] = api_key
        captured["provider"] = provider_type
        captured["model"] = model
        return _StubPolicyProvider()

    monkeypatch.setattr(main, "get_llm_provider", fake_get_llm_provider)
    return captured


def _bodies_contain_key(obj, key):
    """Recursively scan a JSON-serializable body for leaked key material."""
    text = json.dumps(obj, default=str)
    return key in text


class TestCatalog:
    def test_seeded_from_provider_models(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        entries = client.get("/api/providers/catalog").json()
        assert len(entries) > 0
        assert all({"provider", "model", "enabled"} <= set(e) for e in entries)
        assert all(e["enabled"] for e in entries)

    def test_admin_can_disable_non_admin_cannot(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        entry = client.get("/api/providers/catalog").json()[0]
        response = client.put(
            "/api/providers/catalog",
            json={"provider": entry["provider"], "model": entry["model"], "enabled": False},
        )
        assert response.status_code == 403
        _as_user("boss")
        updated = client.put(
            "/api/providers/catalog",
            json={"provider": entry["provider"], "model": entry["model"], "enabled": False},
        ).json()
        assert updated["enabled"] is False


class TestProfiles:
    def _create(self, client, **overrides):
        body = {
            "name": "work-muse",
            "provider": "muse",
            "model": "muse-spark-1.3-contributor",
            "api_key": "sk-test-aaaabbbbccccdddd",
        }
        body.update(overrides)
        return client.post("/api/profiles", json=body)

    def test_create_returns_no_key_material(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        response = self._create(client)
        assert response.status_code == 201
        body = response.json()
        assert body["has_key"] is True
        assert body["key_hint"] == "dddd"
        assert not _bodies_contain_key(body, "sk-test-aaaabbbbccccdddd")
        assert "api_key" not in body and "key_enc" not in body

    def test_list_never_leaks_keys(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        self._create(client)
        for profile in client.get("/api/profiles").json():
            assert "api_key" not in profile and "key_enc" not in profile

    def test_first_profile_becomes_active(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        assert self._create(client).json()["active"] is True
        second = self._create(client, name="spare").json()
        assert second["active"] is False
        activated = client.post(f"/api/profiles/{second['id']}/activate").json()
        assert activated["active"] is True

    def test_name_validation_and_uniqueness(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        assert self._create(client).status_code == 201
        assert self._create(client).status_code == 409
        assert self._create(client, name="bad/name!").status_code in (400, 422)

    def test_disabled_model_rejected(self, _as_user):
        _as_user("boss")
        client = TestClient(main.app)
        client.put(
            "/api/providers/catalog",
            json={"provider": "muse", "model": "muse-spark-1.3-contributor", "enabled": False},
        )
        _as_user("alice")
        response = self._create(client)
        assert response.status_code == 400

    def test_users_cannot_touch_each_others_profiles(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        profile_id = self._create(client).json()["id"]
        _as_user("mallory")
        assert client.get("/api/profiles").json() == []
        assert client.delete(f"/api/profiles/{profile_id}").status_code == 404
        assert client.post(f"/api/profiles/{profile_id}/activate").status_code == 404

    def test_update_and_delete(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        profile_id = self._create(client).json()["id"]
        renamed = client.patch(
            f"/api/profiles/{profile_id}", json={"name": "renamed"}
        ).json()
        assert renamed["name"] == "renamed"
        rotated = client.patch(
            f"/api/profiles/{profile_id}", json={"api_key": "sk-test-zzzz9999"}
        ).json()
        assert rotated["key_hint"] == "9999"
        assert not _bodies_contain_key(rotated, "sk-test-zzzz9999")
        assert client.delete(f"/api/profiles/{profile_id}").status_code == 204
        assert client.get("/api/profiles").json() == []


class TestProfileEvaluation:
    def _submit(self, client, **overrides):
        body = {
            "request_text": "I need to read objects from the example bucket for debugging.",
            "provider": "muse",
            "duration": 2,
        }
        body.update(overrides)
        return client.post("/api/requests", json=body)

    def test_submit_with_profile_uses_stored_key(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        profile_id = (
            client.post(
                "/api/profiles",
                json={
                    "name": "work-muse",
                    "provider": "muse",
                    "model": "muse-spark-1.3-contributor",
                    "api_key": "sk-test-aaaabbbbccccdddd",
                },
            ).json()["id"]
        )
        body = self._submit(client, profile_id=profile_id).json()
        assert _stub_llm["api_key"] == "sk-test-aaaabbbbccccdddd"
        assert _stub_llm["provider"] == "muse"
        assert _stub_llm["model"] == "muse-spark-1.3-contributor"
        assert body[0]["provider"] == "muse"
        assert body[0]["model"] == "muse-spark-1.3-contributor"
        events = main.get_audit_log().read(request_id=body[0]["id"])
        submitted = next(e for e in events if e["event"] == "submitted")
        assert submitted["profile"] == "profile:work-muse"
        assert not _bodies_contain_key(events, "sk-test-aaaabbbbccccdddd")

    def test_cannot_use_another_users_profile(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        profile_id = (
            client.post(
                "/api/profiles",
                json={
                    "name": "work-muse",
                    "provider": "muse",
                    "model": "muse-spark-1.3-contributor",
                    "api_key": "sk-test-aaaabbbbccccdddd",
                },
            ).json()["id"]
        )
        _as_user("mallory")
        response = self._submit(client, profile_id=profile_id)
        assert response.status_code == 404

    def test_disabled_model_rejected_at_submit(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        profile_id = (
            client.post(
                "/api/profiles",
                json={
                    "name": "work-muse",
                    "provider": "muse",
                    "model": "muse-spark-1.3-contributor",
                    "api_key": "sk-test-aaaabbbbccccdddd",
                },
            ).json()["id"]
        )
        _as_user("boss")
        client.put(
            "/api/providers/catalog",
            json={"provider": "muse", "model": "muse-spark-1.3-contributor", "enabled": False},
        )
        _as_user("alice")
        assert self._submit(client, profile_id=profile_id).status_code == 400
