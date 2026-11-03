"""Split-consent workflow: preview, accept-split, full-review, read preservation.

Covers the carol case: a mixed read+write request must never persist as a
surprise split, the user must accept the split or choose one combined
review, and the pending unit must keep the reads it needs to be usable.
"""
import pytest
from fastapi.testclient import TestClient

import main
from llm_service import PolicyResponse
from test_requests import HIGH_UNIT, LOW_UNIT, SAFE_POLICY, _submit


class _StubPolicyProvider:
    def __init__(self, risk="medium", units=None):
        self.risk = risk
        self.units = units

    def generate_policy(self, request_text):
        if self.units is None:
            return [
                PolicyResponse(
                    policy=dict(SAFE_POLICY),
                    risk=self.risk,
                    explanation="stub explanation",
                    approver_note="stub approver note",
                )
            ]
        return [
            PolicyResponse(
                policy=dict(unit["policy"]),
                risk=unit["risk"],
                explanation=unit.get("explanation", ""),
                approver_note=unit.get("approver_note", ""),
                label=unit.get("label", ""),
                narrative=dict(unit.get("narrative", {})),
            )
            for unit in self.units
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
    state = {"risk": "medium", "units": None}

    def fake_get_llm_provider(provider_type=None, model=None, api_key=None):
        return _StubPolicyProvider(risk=state["risk"], units=state["units"])

    monkeypatch.setattr(main, "get_llm_provider", fake_get_llm_provider)
    return state


def _preview(client, **overrides):
    body = {
        "request_text": "I need to scan the analytics bucket and write the rollup back.",
        "provider": "muse",
        "duration": 2,
    }
    body.update(overrides)
    return client.post("/api/requests/preview", json=body)


class TestPreview:
    def test_preview_shows_split_without_persisting(self, _as_user, _stub_llm):
        _stub_llm["units"] = [LOW_UNIT, HIGH_UNIT]
        _as_user("carol")
        client = TestClient(main.app)
        response = _preview(client)
        assert response.status_code == 200
        units = response.json()
        assert len(units) == 2
        assert units[0]["auto_approved"] is True
        assert units[1]["auto_approved"] is False
        # Nothing persisted: no rows, no audit.
        assert main.get_request_store().list(requester="carol") == []

    def test_preview_single_unit(self, _as_user, _stub_llm):
        _as_user("carol")
        client = TestClient(main.app)
        units = _preview(client).json()
        assert len(units) == 1


class TestConfirmedSplit:
    def test_accepted_units_persist_without_second_llm(self, _as_user, _stub_llm, monkeypatch):
        _stub_llm["units"] = [LOW_UNIT, HIGH_UNIT]
        _as_user("carol")
        client = TestClient(main.app)
        preview = _preview(client).json()
        calls = []

        orig = main._evaluate_access_request

        def counting(*args, **kwargs):
            calls.append(1)
            return orig(*args, **kwargs)

        monkeypatch.setattr(main, "_evaluate_access_request", counting)
        response = client.post(
            "/api/requests",
            json={
                "request_text": "I need to scan the analytics bucket and write the rollup back.",
                "provider": "muse",
                "duration": 2,
                "confirmed_units": preview,
            },
        )
        assert response.status_code == 201
        assert calls == []
        rows = response.json()
        assert len(rows) == 2
        assert rows[0]["label"] == LOW_UNIT["label"]
        assert rows[1]["label"] == HIGH_UNIT["label"]
        assert rows[0]["batch_id"] == rows[1]["batch_id"] == rows[0]["id"]

    def test_full_review_combines_into_one_pending(self, _as_user, _stub_llm):
        _stub_llm["units"] = [LOW_UNIT, HIGH_UNIT]
        _as_user("carol")
        client = TestClient(main.app)
        preview = _preview(client).json()
        response = client.post(
            "/api/requests",
            json={
                "request_text": "I need to scan the analytics bucket and write the rollup back.",
                "provider": "muse",
                "duration": 2,
                "full_review": True,
                "confirmed_units": preview,
            },
        )
        assert response.status_code == 201
        rows = response.json()
        assert len(rows) == 1
        assert rows[0]["status"] == "pending_review"
        assert rows[0]["auto_approved"] is False
        assert rows[0]["label"] == "Combined full review"
        events = main.get_audit_log().read(request_id=rows[0]["id"])
        submitted = next(e for e in events if e["event"] == "submitted")
        assert submitted.get("full_review") is True

    def test_full_review_without_units_combines_llm_split(self, _as_user, _stub_llm):
        _stub_llm["units"] = [LOW_UNIT, HIGH_UNIT]
        _as_user("carol")
        client = TestClient(main.app)
        rows = client.post(
            "/api/requests",
            json={
                "request_text": "I need to scan the analytics bucket and write the rollup back.",
                "provider": "muse",
                "duration": 2,
                "full_review": True,
            },
        ).json()
        assert len(rows) == 1
        assert rows[0]["status"] == "pending_review"


class TestReadPreservation:
    def test_pending_unit_keeps_prerequisite_reads(self, _as_user, _stub_llm):
        read_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:GetObject"],
                    "Resource": ["arn:aws:s3:::analytics/*"],
                }
            ],
        }
        write_policy = {
            "Version": "2012-10-17",
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": ["s3:PutObject"],
                    "Resource": ["arn:aws:s3:::analytics/*"],
                }
            ],
        }
        _stub_llm["units"] = [
            {**LOW_UNIT, "policy": read_policy},
            {**HIGH_UNIT, "policy": write_policy},
        ]
        _as_user("carol")
        client = TestClient(main.app)
        rows = _submit(client).json()
        assert len(rows) == 2
        pending = next(r for r in rows if r["status"] == "pending_review")
        actions = [
            a
            for stmt in pending["policy"].get("Statement", [])
            for a in (stmt.get("Action", []))
        ]
        assert "s3:GetObject" in actions
        assert "s3:PutObject" in actions


class TestBatchEndpoint:
    def test_batch_returns_siblings_in_order(self, _as_user, _stub_llm):
        _stub_llm["units"] = [LOW_UNIT, HIGH_UNIT]
        _as_user("carol")
        client = TestClient(main.app)
        rows = _submit(client).json()
        batch_id = rows[0]["batch_id"]
        response = client.get(f"/api/requests/batch/{batch_id}")
        assert response.status_code == 200
        siblings = response.json()
        assert [r["id"] for r in siblings] == sorted(r["id"] for r in rows)
        assert all(r["batch_id"] == batch_id for r in siblings)

    def test_batch_forbidden_to_stranger(self, _as_user, _stub_llm):
        _stub_llm["units"] = [LOW_UNIT, HIGH_UNIT]
        _as_user("carol")
        client = TestClient(main.app)
        batch_id = _submit(client).json()[0]["batch_id"]
        _as_user("mallory")
        assert client.get(f"/api/requests/batch/{batch_id}").status_code == 403


class TestRecordBatch:
    def test_record_accepts_split_units(self, _as_user, monkeypatch):
        _as_user("alice")

        def no_llm(*args, **kwargs):
            raise AssertionError("record must not call the LLM")

        monkeypatch.setattr(main, "get_llm_provider", no_llm)
        scoped_write = {
            "label": "write scoped rollup",
            "policy": {
                "Version": "2012-10-17",
                "Statement": [
                    {
                        "Effect": "Allow",
                        "Action": ["s3:PutObject"],
                        "Resource": ["arn:aws:s3:::analytics/*"],
                    }
                ],
            },
            "risk": "medium",
            "explanation": "scoped write",
            "approver_note": "needs review",
        }
        client = TestClient(main.app)
        response = client.post(
            "/api/requests/record",
            json={
                "request_text": "Scan the analytics bucket and write the rollup back, twice the detail.",
                "provider": "muse",
                "duration": 2,
                "policy": dict(SAFE_POLICY),
                "risk": "low",
                "units": [LOW_UNIT, scoped_write],
            },
        )
        assert response.status_code == 201
        rows = response.json()
        assert len(rows) == 2
        assert rows[0]["status"] == "approved"
        assert rows[1]["status"] == "pending_review"


class TestGeneratePolicyFlags:
    def test_truncated_split_is_flagged(self, _as_user, _stub_llm):
        _stub_llm["units"] = [LOW_UNIT, HIGH_UNIT]
        _as_user("carol")
        client = TestClient(main.app)
        body = client.post(
            "/api/generate-policy",
            json={"request_text": "Scan the analytics bucket and write the rollup back, in detail.", "provider": "muse", "duration": 2},
        ).json()
        assert body["single_grant_only"] is True
        assert body["total_units"] == 2
        assert body["unit_labels"] == [LOW_UNIT["label"], HIGH_UNIT["label"]]
