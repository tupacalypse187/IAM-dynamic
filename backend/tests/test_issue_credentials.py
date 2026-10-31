"""Guardrail tests for POST /api/issue-credentials via FastAPI TestClient."""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def _auth_disabled(monkeypatch):
    """Bypass auth so endpoint tests pass with or without a .env hash."""
    monkeypatch.setattr(main, "auth_service", None)


def _policy(action, resource, effect="Allow"):
    return {
        "Version": "2012-10-17",
        "Statement": [{"Effect": effect, "Action": action, "Resource": resource}],
    }


def _mock_sts(monkeypatch):
    """Replace STS with a stub; return the list of policies it was called with."""
    calls = []

    def fake_assume_role_with_policy(policy, duration_hours, session_name="x"):
        calls.append(policy)
        return {
            "AccessKeyId": "AKIAEXAMPLE",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": datetime(2026, 1, 1, tzinfo=timezone.utc),
        }

    monkeypatch.setattr(
        main.sts_service, "assume_role_with_policy", fake_assume_role_with_policy
    )
    return calls


def _post(client, policy, approved=True):
    return client.post(
        "/api/issue-credentials",
        json={"policy": policy, "duration": 2, "approved": approved},
    )


def test_unapproved_returns_403_without_calling_sts(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    policy = _policy("s3:GetObject", "arn:aws:s3:::my-bucket/*")
    response = _post(client, policy, approved=False)
    assert response.status_code == 403
    assert calls == []


def test_full_admin_action_rejected(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    response = _post(client, _policy("*", "*"))
    assert response.status_code == 400
    assert calls == []


def test_wildcard_action_rejected(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    response = _post(client, _policy("s3:*", "arn:aws:s3:::my-bucket/*"))
    assert response.status_code == 400
    assert calls == []


def test_escalation_action_rejected(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    response = _post(
        client, _policy("iam:PassRole", "arn:aws:iam::123456789012:role/x")
    )
    assert response.status_code == 400
    assert calls == []


def test_star_resource_with_write_action_rejected(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    response = _post(client, _policy("s3:PutObject", "*"))
    assert response.status_code == 400
    assert calls == []


def test_star_resource_with_read_only_action_allowed(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    response = _post(client, _policy("s3:GetObject", "*"))
    assert response.status_code == 200, response.text
    assert len(calls) == 1
    assert response.json()["access_key_id"] == "AKIAEXAMPLE"


def test_not_action_rejected(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "NotAction": "s3:DeleteBucket", "Resource": "*"}
        ],
    }
    response = _post(client, policy)
    assert response.status_code == 400
    assert calls == []


def test_not_resource_rejected(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": "s3:GetObject",
                "NotResource": ["arn:aws:s3:::other-bucket/*"],
            }
        ],
    }
    response = _post(client, policy)
    assert response.status_code == 400
    assert calls == []


def test_scoped_read_action_calls_sts(monkeypatch):
    calls = _mock_sts(monkeypatch)
    client = TestClient(main.app)
    policy = _policy("s3:GetObject", "arn:aws:s3:::my-bucket/*")
    response = _post(client, policy)
    assert response.status_code == 200, response.text
    assert calls == [policy]
