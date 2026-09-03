"""API endpoint tests via FastAPI TestClient."""
import pytest
from fastapi.testclient import TestClient

import main


def llm_config():
    # main.py builds its own config via load_config(), distinct from the
    # config.py singleton — patch the instance the app actually uses.
    return main.config.llm


@pytest.fixture(autouse=True)
def _auth_disabled(monkeypatch):
    """
    Protected endpoints bypass auth only when no auth service is
    configured. Force that state so these tests pass deterministically
    even when a developer's .env enables authentication.
    """
    monkeypatch.setattr(main, "auth_service", None)


class TestHealth:
    def test_health_endpoint(self):
        client = TestClient(main.app)
        response = client.get("/health")
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "healthy"
        assert "timestamp" in body


class TestProvidersEndpoint:
    def test_providers_gated_on_api_keys(self, monkeypatch):
        monkeypatch.setattr(llm_config(), "zai_api_key", "test-key")
        monkeypatch.setattr(llm_config(), "muse_api_key", "test-key")
        monkeypatch.setattr(llm_config(), "openrouter_api_key", None)

        client = TestClient(main.app)
        response = client.get("/config/providers")
        assert response.status_code == 200

        body = response.json()
        provider_ids = [p["id"] for p in body["providers"]]
        assert "zhipu" in provider_ids
        assert "muse" in provider_ids
        assert "openrouter" not in provider_ids, "must be hidden when key missing"
        assert body["account_id"] == main.config.aws.account_id

    def test_provider_entry_shape(self, monkeypatch):
        monkeypatch.setattr(llm_config(), "zai_api_key", "test-key")
        client = TestClient(main.app)
        body = client.get("/config/providers").json()
        zhipu = next(p for p in body["providers"] if p["id"] == "zhipu")
        assert zhipu["name"] == "Z.AI GLM"
        assert zhipu["model"] == main.config.llm.zai_model
        assert any(m["id"] == "glm-5.3" for m in zhipu["models"])


class TestGeneratePolicy:
    def test_missing_key_returns_400_with_help(self):
        client = TestClient(main.app)
        response = client.post(
            "/api/generate-policy",
            json={"request_text": "read a bucket", "provider": "openrouter"},
        )
        assert response.status_code == 400
        assert "API Key Missing" in response.json()["detail"]
