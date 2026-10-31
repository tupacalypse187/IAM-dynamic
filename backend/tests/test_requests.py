"""Review workflow tests: submit, review, resubmit, activate, audit.

The LLM and STS layers are stubbed — these tests cover routing, role
gating, the status machine, and the JSONL audit trail, never real APIs.
"""
from datetime import datetime, timezone

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
        return PolicyResponse(
            policy=dict(SAFE_POLICY),
            risk=self.risk,
            explanation="stub explanation",
            approver_note="stub approver note",
        )


@pytest.fixture()
def _as_user(monkeypatch):
    """Run requests as a chosen user; 'boss' is the admin."""
    monkeypatch.setattr(main, "auth_service", None)
    monkeypatch.setattr(main, "_is_admin", lambda username: username == "boss")

    def use(username):
        main.app.dependency_overrides[main.get_current_user] = lambda: username

    yield use
    main.app.dependency_overrides.clear()


@pytest.fixture()
def _stub_llm(monkeypatch):
    """Stub LLM evaluation with a controllable risk level."""
    state = {"risk": "medium"}

    def fake_get_llm_provider(provider_type=None, model=None, api_key=None):
        return _StubPolicyProvider(risk=state["risk"])

    monkeypatch.setattr(main, "get_llm_provider", fake_get_llm_provider)
    return state


def _submit(client, **overrides):
    body = {
        "request_text": "I need to read objects from the example bucket for debugging.",
        "provider": "muse",
        "duration": 2,
    }
    body.update(overrides)
    return client.post("/api/requests", json=body)


class TestSubmit:
    def test_medium_risk_queues_for_review(self, _as_user, _stub_llm):
        _as_user("alice")
        response = TestClient(main.app)
        result = _submit(response)
        assert result.status_code == 201
        body = result.json()
        assert body["requester"] == "alice"
        assert body["status"] == "pending_review"
        assert body["risk"] == "medium"
        assert body["policy"] == SAFE_POLICY
        assert body["auto_approved"] is False
        assert body["reviewer"] is None

    def test_low_risk_approved_but_creates_no_credentials(self, _as_user, _stub_llm):
        _stub_llm["risk"] = "low"
        _as_user("alice")
        client = TestClient(main.app)
        body = _submit(client).json()
        assert body["status"] == "approved"
        assert body["auto_approved"] is True
        # Approval alone must not issue anything: activation is still required.
        assert body["credentials_expires_at"] is None
        events = main.get_audit_log().read(request_id=body["id"])
        kinds = {e["event"] for e in events}
        assert {"submitted", "auto_approved"} <= kinds
        auto = next(e for e in events if e["event"] == "auto_approved")
        assert auto["actor"] == "system"
        assert auto["actor_role"] == "automated"

    def test_queued_audit_trail(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        body = _submit(client).json()
        events = main.get_audit_log().read(request_id=body["id"])
        kinds = {e["event"] for e in events}
        assert {"submitted", "queued_for_review"} <= kinds


class TestCatalogEnforcement:
    """An admin-disabled catalog pair must block server-default evaluation."""

    def test_disabled_pair_blocked(self, _as_user, _stub_llm):
        _as_user("alice")
        main.get_profile_store().set_catalog_enabled(
            "muse", "muse-spark-1.3-contributor", False
        )
        client = TestClient(main.app)
        response = _submit(client, model="muse-spark-1.3-contributor")
        assert response.status_code == 400

    def test_disabled_pair_blocked_via_alias(self, _as_user, _stub_llm):
        _as_user("alice")
        main.get_profile_store().set_catalog_enabled(
            "muse", "muse-spark-1.3-contributor", False
        )
        client = TestClient(main.app)
        response = _submit(
            client, provider="meta", model="muse-spark-1.3-contributor"
        )
        assert response.status_code == 400

    def test_other_model_of_provider_still_allowed(self, _as_user, _stub_llm):
        _as_user("alice")
        main.get_profile_store().set_catalog_enabled(
            "muse", "muse-spark-1.3-contributor", False
        )
        client = TestClient(main.app)
        response = _submit(client, model="muse-wonder-1.0")
        assert response.status_code == 201

    def test_all_disabled_blocks_unset_model(self, _as_user, _stub_llm):
        _as_user("alice")
        store = main.get_profile_store()
        for entry in store.list_catalog():
            if entry["provider"] == "muse":
                store.set_catalog_enabled("muse", entry["model"], False)
        client = TestClient(main.app)
        response = _submit(client)
        assert response.status_code == 400

    def test_unknown_model_id_passes_through(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        response = _submit(client, model="custom-future-model")
        assert response.status_code == 201


class TestRecord:
    def _record_body(self, **overrides):
        body = {
            "request_text": "I need to read objects from the example bucket for debugging.",
            "provider": "muse",
            "duration": 2,
            "policy": dict(SAFE_POLICY),
            "risk": "medium",
            "explanation": "stub",
            "approver_note": "stub",
        }
        body.update(overrides)
        return body

    def test_record_persists_without_llm(self, _as_user, monkeypatch):
        _as_user("alice")

        def no_llm(*args, **kwargs):
            raise AssertionError("record must not call the LLM")

        monkeypatch.setattr(main, "get_llm_provider", no_llm)
        client = TestClient(main.app)
        response = client.post("/api/requests/record", json=self._record_body())
        assert response.status_code == 201
        assert response.json()["status"] == "pending_review"

    def test_record_normalizes_unknown_risk(self, _as_user, monkeypatch):
        _as_user("alice")
        monkeypatch.setattr(
            main, "get_llm_provider", lambda *a, **k: (_ for _ in ()).throw(AssertionError("no LLM"))
        )
        client = TestClient(main.app)
        body = client.post(
            "/api/requests/record", json=self._record_body(risk="Mystery")
        ).json()
        assert body["risk"] == "medium"
        assert body["auto_approved"] is False

    def test_record_rejects_overly_broad_policy(self, _as_user):
        _as_user("alice")
        client = TestClient(main.app)
        broad = {
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Allow", "Action": "*", "Resource": "*"}],
        }
        response = client.post(
            "/api/requests/record", json=self._record_body(policy=broad)
        )
        assert response.status_code == 400


class TestReview:
    def test_non_admin_cannot_review(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        response = client.post(
            f"/api/requests/{request_id}/review",
            json={"decision": "approve"},
        )
        assert response.status_code == 403

    def test_approve_records_reviewer(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        _as_user("boss")
        response = client.post(
            f"/api/requests/{request_id}/review",
            json={"decision": "approve", "feedback": "Looks scoped. Approved."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "approved"
        assert body["reviewer"] == "boss"
        events = main.get_audit_log().read(request_id=request_id)
        approved = next(e for e in events if e["event"] == "approved")
        assert approved["actor"] == "boss"

    def test_deny_requires_feedback(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        _as_user("boss")
        response = client.post(
            f"/api/requests/{request_id}/review", json={"decision": "deny"}
        )
        assert response.status_code == 400
        assert "Feedback is required" in response.json()["detail"]

    def test_send_back_then_resubmit_bumps_revision(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        _as_user("boss")
        sent_back = client.post(
            f"/api/requests/{request_id}/review",
            json={"decision": "changes_requested", "feedback": "Scope to one bucket."},
        )
        assert sent_back.json()["status"] == "changes_requested"
        _as_user("alice")
        response = client.post(
            f"/api/requests/{request_id}/resubmit",
            json={"request_text": "I need to read objects from the example bucket only."},
        )
        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "pending_review"
        assert body["revision"] == 2
        assert body["reviewer"] is None

    def test_double_review_rejected(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        _as_user("boss")
        client.post(f"/api/requests/{request_id}/review", json={"decision": "approve"})
        again = client.post(
            f"/api/requests/{request_id}/review", json={"decision": "deny", "feedback": "x"}
        )
        assert again.status_code == 400


class TestActivate:
    def test_pending_request_cannot_be_activated(self, _as_user, _stub_llm, monkeypatch):
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        issued = []
        monkeypatch.setattr(
            main.sts_service,
            "assume_role_with_policy",
            lambda policy, duration, **kwargs: issued.append((policy, duration)),
        )
        response = client.post(f"/api/requests/{request_id}/activate")
        assert response.status_code == 400
        assert issued == []

    def test_activate_issues_stored_policy_once(self, _as_user, _stub_llm, monkeypatch):
        _stub_llm["risk"] = "low"
        _as_user("alice")
        client = TestClient(main.app)
        stored = _submit(client).json()
        calls = []

        def fake_assume(policy, duration, **kwargs):
            calls.append((policy, duration))
            return {
                "AccessKeyId": "AKIAEXAMPLE",
                "SecretAccessKey": "secret",
                "SessionToken": "token",
                "Expiration": datetime.now(timezone.utc),
            }

        monkeypatch.setattr(main.sts_service, "assume_role_with_policy", fake_assume)
        monkeypatch.setattr(main, "send_audit_notification", lambda **kwargs: None)
        response = client.post(f"/api/requests/{stored['id']}/activate")
        assert response.status_code == 200
        assert response.json()["access_key_id"] == "AKIAEXAMPLE"
        # The reviewed policy — not a caller-supplied one — reaches STS.
        assert calls == [(SAFE_POLICY, stored["duration"])]
        again = client.post(f"/api/requests/{stored['id']}/activate")
        assert again.status_code == 400
        assert len(calls) == 1
        events = main.get_audit_log().read(request_id=stored["id"])
        activated = next(e for e in events if e["event"] == "activated")
        assert activated["actor"] == "alice"
        assert activated["reviewer"] == "system (auto-approved)"

    def test_only_owner_can_activate(self, _as_user, _stub_llm):
        _stub_llm["risk"] = "low"
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        _as_user("mallory")
        response = client.post(f"/api/requests/{request_id}/activate")
        assert response.status_code == 403


class TestBaseRoleSelection:
    def _creds(self, **kwargs):
        return {
            "AccessKeyId": "AKIAEXAMPLE",
            "SecretAccessKey": "secret",
            "SessionToken": "token",
            "Expiration": datetime.now(timezone.utc),
        }

    def _activate_with_capture(self, monkeypatch, arns):
        # Pin every base-role ARN first: a developer's real .env must never
        # leak into these tests (hermetic-test rule).
        for key in (
            "base_role_readonly",
            "base_role_developer",
            "base_role_support",
            "base_role_analyst",
            "base_role_auditor",
            "base_role_admin",
        ):
            monkeypatch.setattr(main.config.aws, key, "")
        for key, value in arns.items():
            monkeypatch.setattr(main.config.aws, key, value)
        calls = []

        def fake_assume(policy, duration, **kwargs):
            calls.append(kwargs.get("role_arn"))
            return self._creds()

        monkeypatch.setattr(main.sts_service, "assume_role_with_policy", fake_assume)
        monkeypatch.setattr(main, "send_audit_notification", lambda **kwargs: None)
        return calls

    def test_readonly_policy_uses_readonly_base(self, _as_user, _stub_llm, monkeypatch):
        _stub_llm["risk"] = "low"
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        calls = self._activate_with_capture(
            monkeypatch,
            {"base_role_readonly": "arn:aws:iam::123456789012:role/ro"},
        )
        assert client.post(f"/api/requests/{request_id}/activate").status_code == 200
        assert calls == ["arn:aws:iam::123456789012:role/ro"]
        events = main.get_audit_log().read(request_id=request_id)
        activated = next(e for e in events if e["event"] == "activated")
        assert activated["base_role"] == "readonly"

    def test_unset_arns_keep_legacy_behavior(self, _as_user, _stub_llm, monkeypatch):
        _stub_llm["risk"] = "low"
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        calls = self._activate_with_capture(monkeypatch, {})
        assert client.post(f"/api/requests/{request_id}/activate").status_code == 200
        assert calls == [None]
        events = main.get_audit_log().read(request_id=request_id)
        activated = next(e for e in events if e["event"] == "activated")
        assert activated["base_role"] == "legacy"

    def test_write_policy_selects_developer_base(self, _as_user, monkeypatch):
        _as_user("alice")

        def fake_factory(provider_type=None, model=None, api_key=None):
            stub = _StubPolicyProvider()
            stub.policy = {
                "Version": "2012-10-17",
                "Statement": [
                    {"Effect": "Allow", "Action": ["s3:PutObject"], "Resource": ["*"]}
                ],
            }
            stub.risk = "medium"
            return stub

        monkeypatch.setattr(main, "get_llm_provider", fake_factory)
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        _as_user("boss")
        client.post(f"/api/requests/{request_id}/review", json={"decision": "approve"})
        _as_user("alice")
        calls = self._activate_with_capture(
            monkeypatch,
            {"base_role_developer": "arn:aws:iam::123456789012:role/dev"},
        )
        assert client.post(f"/api/requests/{request_id}/activate").status_code == 200
        assert calls == ["arn:aws:iam::123456789012:role/dev"]


class TestBaseRoleClassifier:
    def test_readonly_actions(self):
        from services.sts_service import select_base_role_class

        policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject", "s3:ListBucket", "ec2:Describe*"],
                    "Resource": ["*"],
                }
            ],
        }
        assert select_base_role_class(policy) == "readonly"

    def test_write_action_selects_developer(self):
        from services.sts_service import select_base_role_class

        for actions in (
            ["s3:PutObject"],
            ["s3:*"],
            ["*"],
            ["iam:CreateRole"],
        ):
            policy = {
                "Version": "2012-10-17",
                "Statement": [{"Effect": "Allow", "Action": actions, "Resource": ["*"]}],
            }
            assert select_base_role_class(policy) == "developer"

    def test_unprovable_shapes_select_developer(self):
        from services.sts_service import select_base_role_class

        assert select_base_role_class({}) == "developer"
        assert select_base_role_class({"Statement": []}) == "developer"
        assert select_base_role_class("nope") == "developer"
        deny_only = {
            "Version": "2012-10-17",
            "Statement": [{"Effect": "Deny", "Action": ["s3:*"], "Resource": ["*"]}],
        }
        assert select_base_role_class(deny_only) == "developer"
        not_action = {
            "Version": "2012-10-17",
            "Statement": [
                {"Effect": "Allow", "NotAction": ["s3:GetObject"], "Resource": ["*"]}
            ],
        }
        assert select_base_role_class(not_action) == "developer"


class TestVisibility:
    def test_users_see_only_theirs_admins_see_all(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        _submit(client)
        _as_user("mallory")
        _submit(client)
        assert len(client.get("/api/requests").json()) == 1
        _as_user("boss")
        assert len(client.get("/api/requests").json()) == 2
        assert len(client.get("/api/requests?mine=true").json()) == 0

    def test_user_cannot_open_others_request(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        request_id = _submit(client).json()["id"]
        _as_user("mallory")
        assert client.get(f"/api/requests/{request_id}").status_code == 403

    def test_audit_requires_admin(self, _as_user, _stub_llm):
        _as_user("alice")
        client = TestClient(main.app)
        _submit(client)
        assert client.get("/api/audit").status_code == 403
        _as_user("boss")
        response = client.get("/api/audit")
        assert response.status_code == 200
        assert any(e["event"] == "submitted" for e in response.json())
