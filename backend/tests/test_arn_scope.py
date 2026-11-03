"""ARN scope pinning: models must not ship '*' region/account segments.

The prompt names this deployment's account/region, and the deterministic
normalizer pins any starred segments server-side before routing or
persistence (Carol's DynamoDB `arn:aws:dynamodb:*:*` case).
"""
import pytest
from fastapi.testclient import TestClient

import main
from llm_service import (
    PolicyResponse,
    normalize_policy_scope,
    system_instruction,
)

STARRED = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Sid": "StageAnalyticsWrite",
            "Effect": "Allow",
            "Action": ["dynamodb:PutItem", "dynamodb:UpdateItem"],
            "Resource": ["arn:aws:dynamodb:*:*:table/my-data-dump-scan"],
        },
        {
            "Sid": "StageAnalyticsRead",
            "Effect": "Allow",
            "Action": ["dynamodb:Query", "dynamodb:Scan"],
            "Resource": [
                "arn:aws:dynamodb:*:*:table/my-data-dump-scan",
                "arn:aws:dynamodb:*:*:table/my-data-dump-scan/index/*",
            ],
        },
    ],
}


class TestPromptScope:
    def test_names_account_and_region(self, monkeypatch):
        monkeypatch.setenv("AWS_ACCOUNT_ID", "467266701745")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        text = system_instruction()
        assert "467266701745" in text
        assert "us-east-1" in text
        assert "arn:aws:dynamodb:us-east-1:467266701745:table/Name" in text

    def test_falls_back_without_account(self, monkeypatch):
        monkeypatch.delenv("AWS_ACCOUNT_ID", raising=False)
        text = system_instruction()
        assert "never '*' for those segments" in text
        assert "467266701745" not in text


class TestNormalize:
    def test_pins_star_segments(self):
        out = normalize_policy_scope(STARRED, account_id="467266701745", region="us-east-1")
        resources = [r for s in out["Statement"] for r in s["Resource"]]
        assert resources == [
            "arn:aws:dynamodb:us-east-1:467266701745:table/my-data-dump-scan",
            "arn:aws:dynamodb:us-east-1:467266701745:table/my-data-dump-scan",
            "arn:aws:dynamodb:us-east-1:467266701745:table/my-data-dump-scan/index/*",
        ]

    def test_leaves_bare_star_and_concrete_arns(self):
        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "Action": ["s3:GetObject"], "Resource": "*"},
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": ["arn:aws:s3:::example-bucket/*", "not-an-arn"],
                },
            ],
        }
        out = normalize_policy_scope(policy, account_id="467266701745", region="us-east-1")
        assert out["Statement"][0]["Resource"] == "*"
        assert out["Statement"][1]["Resource"] == ["arn:aws:s3:::example-bucket/*", "not-an-arn"]

    def test_single_string_resource_and_shape(self):
        policy = {
            "Version": "2012-10-17",
            "Statement": {
                "Effect": "Allow",
                "Action": ["dynamodb:Query"],
                "Resource": "arn:aws:dynamodb:*:*:table/T",
            },
        }
        out = normalize_policy_scope(policy, account_id="A", region="R")
        assert isinstance(out["Statement"], dict)
        assert out["Statement"]["Resource"] == "arn:aws:dynamodb:R:A:table/T"

    def test_unknown_account_leaves_account_stars(self, monkeypatch):
        monkeypatch.delenv("AWS_ACCOUNT_ID", raising=False)
        out = normalize_policy_scope(STARRED, account_id="", region="us-east-1")
        assert out["Statement"][0]["Resource"] == ["arn:aws:dynamodb:us-east-1:*:table/my-data-dump-scan"]


class _StubPolicyProvider:
    def __init__(self, policy):
        self.policy = policy

    def generate_policy(self, request_text):
        return [
            PolicyResponse(
                policy=dict(self.policy),
                risk="medium",
                explanation="stub",
                approver_note="stub",
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


class TestSubmitPinsScope:
    def test_starred_arn_persisted_pinned(self, _as_user, monkeypatch):
        monkeypatch.setenv("AWS_ACCOUNT_ID", "467266701745")
        monkeypatch.setenv("AWS_REGION", "us-east-1")
        monkeypatch.setattr(
            main, "get_llm_provider", lambda *a, **k: _StubPolicyProvider(STARRED)
        )
        _as_user("carol")
        body = TestClient(main.app).post(
            "/api/requests",
            json={
                "request_text": "Query and write the my-data-dump-scan DynamoDB table for analytics with full detail.",
                "provider": "muse",
                "duration": 2,
            },
        ).json()[0]
        resources = [r for s in body["policy"]["Statement"] for r in s["Resource"]]
        assert all(":*:*:" not in r for r in resources)
        assert resources[0] == "arn:aws:dynamodb:us-east-1:467266701745:table/my-data-dump-scan"
