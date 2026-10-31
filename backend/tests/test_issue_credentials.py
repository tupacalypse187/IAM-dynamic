"""Guardrail tests for POST /api/issue-credentials.

Verifies that credential issuance requires approval and rejects
full-admin session policies server-side, without calling AWS STS.
"""
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture(autouse=True)
def _auth_disabled(monkeypatch):
    monkeypatch.setattr(main, "auth_service", None)


def _fake_sts(monkeypatch):
    """Replace STS with a recording fake; returns the call log."""
    calls = []
    expiration = datetime(2030, 1, 1, tzinfo=timezone.utc)

    def fake_assume_role(policy, duration, session_name="gemini-jit-session"):
        calls.append({"policy": policy, "duration": duration})
        return {
            "AccessKeyId": "AKIAEXAMPLE",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": expiration,
        }

    monkeypatch.setattr(
        main.sts_service, "assume_role_with_policy", fake_assume_role
    )
    return calls


def _scoped_policy():
    return {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": "arn:aws:s3:::example-bucket/*",
            }
        ],
    }


def _admin_policy_string_action():
    return {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Allow", "Action": "*", "Resource": "*"}
        ],
    }


def test_unapproved_request_rejected_and_sts_never_called(monkeypatch):
    calls = _fake_sts(monkeypatch)
    client = TestClient(main.app)
    response = client.post(
        "/api/issue-credentials",
        json={"policy": _scoped_policy(), "duration": 2, "approved": False},
    )
    assert response.status_code == 403
    assert calls == []


def test_unapproved_default_rejected(monkeypatch):
    """approved defaults to False, so omitting it must also be rejected."""
    calls = _fake_sts(monkeypatch)
    client = TestClient(main.app)
    response = client.post(
        "/api/issue-credentials",
        json={"policy": _scoped_policy(), "duration": 2},
    )
    assert response.status_code == 403
    assert calls == []


def test_full_admin_string_action_rejected(monkeypatch):
    calls = _fake_sts(monkeypatch)
    client = TestClient(main.app)
    response = client.post(
        "/api/issue-credentials",
        json={
            "policy": _admin_policy_string_action(),
            "duration": 12,
            "approved": True,
        },
    )
    assert response.status_code == 400
    assert calls == []


def test_full_admin_list_action_rejected(monkeypatch):
    calls = _fake_sts(monkeypatch)
    client = TestClient(main.app)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject", "*:*"],
                "Resource": "*",
            }
        ],
    }
    response = client.post(
        "/api/issue-credentials",
        json={"policy": policy, "duration": 2, "approved": True},
    )
    assert response.status_code == 400
    assert calls == []


def test_deny_wildcard_not_blocked(monkeypatch):
    """A Deny * statement is not a grant, so it must pass the guardrail."""
    calls = _fake_sts(monkeypatch)
    client = TestClient(main.app)
    policy = {
        "Version": "2012-10-17",
        "Statement": [
            {"Effect": "Deny", "Action": "*", "Resource": "*"},
            {
                "Effect": "Allow",
                "Action": ["s3:GetObject"],
                "Resource": "arn:aws:s3:::example-bucket/*",
            },
        ],
    }
    response = client.post(
        "/api/issue-credentials",
        json={"policy": policy, "duration": 2, "approved": True},
    )
    assert response.status_code == 200
    assert len(calls) == 1


def test_approved_scoped_policy_issues_credentials(monkeypatch):
    calls = _fake_sts(monkeypatch)
    client = TestClient(main.app)
    policy = _scoped_policy()
    response = client.post(
        "/api/issue-credentials",
        json={"policy": policy, "duration": 2, "approved": True},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["access_key_id"] == "AKIAEXAMPLE"
    assert len(calls) == 1
    assert calls[0]["policy"] == policy
    assert calls[0]["duration"] == 2
