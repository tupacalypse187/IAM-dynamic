"""One-thread-per-request tests: service threading, store roots, wiring.

Service tests mock the HTTP layer exactly like the existing service suites.
Store tests cover fresh + migrated (v3) databases and concurrent claims.
Wiring tests drive the API with stubbed LLM/STS and fake channel services.
"""
import sqlite3
import threading
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

import main
from services import request_store as rs_mod
from services.request_store import RequestStore
from services.slack_service import SlackService
from services.telegram_service import TelegramService


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


class _FakeAPIResponse:
    """Mimics requests.Response for the Web API / Bot API paths."""

    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeWebhookResponse:
    """Legacy fakes (no .json) still report delivery as success."""

    def raise_for_status(self):
        pass


def _slack_api(monkeypatch, captured, payload=None):
    def fake_post(url, json=None, timeout=None, headers=None):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeAPIResponse(
            payload if payload is not None else {"ok": True, "ts": "1720000000.0001"}
        )

    monkeypatch.setattr("services.slack_service.requests.post", fake_post)


def _telegram_api(monkeypatch, captured, payload=None):
    def fake_post(url, json=None, timeout=None):
        captured["url"] = url
        captured["json"] = json
        return _FakeAPIResponse(
            payload
            if payload is not None
            else {"ok": True, "result": {"message_id": 42}}
        )

    monkeypatch.setattr("services.telegram_service.requests.post", fake_post)


class TestSlackThreading:
    def test_api_disabled_without_token_and_channel(self):
        assert SlackService().api_enabled is False
        assert SlackService(bot_token="xoxb-t").api_enabled is False
        assert SlackService(channel_id="C1").api_enabled is False
        assert SlackService(bot_token="xoxb-t", channel_id="C1").api_enabled is True

    def test_root_post_returns_ts_via_api(self, monkeypatch):
        captured = {}
        _slack_api(monkeypatch, captured)
        service = SlackService(bot_token="xoxb-t", channel_id="C1")
        ts = service.post_thread_root(
            request_ref="req-00007",
            requester="alice",
            risk_level="high",
            request_text="read the bucket",
            status="pending_review",
        )
        assert ts == "1720000000.0001"
        assert captured["url"] == "https://slack.com/api/chat.postMessage"
        assert captured["headers"] == {"Authorization": "Bearer xoxb-t"}
        assert captured["json"]["channel"] == "C1"
        assert "thread_ts" not in captured["json"]
        assert "req-00007" in captured["json"]["text"]
        assert "alice" in str(captured["json"]["blocks"])

    def test_reply_passes_thread_ts(self, monkeypatch):
        captured = {}
        _slack_api(monkeypatch, captured)
        service = SlackService(bot_token="xoxb-t", channel_id="C1")
        assert service.send_decision_notification(
            request_ref="req-00007",
            decision="approved",
            reviewer="boss",
            requester="alice",
            risk_level="medium",
            request_text="read the bucket",
            thread_ts="1720000000.0001",
        ) is True
        assert captured["json"]["thread_ts"] == "1720000000.0001"

    def test_api_failure_returns_false_and_no_ts(self, monkeypatch):
        captured = {}
        _slack_api(monkeypatch, captured, payload={"ok": False, "error": "x"})
        service = SlackService(bot_token="xoxb-t", channel_id="C1")
        assert service.post_thread_root(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="pending_review",
        ) is None
        assert service.send_notification("hi") is False

    def test_webhook_only_ignores_thread_ts_and_stays_top_level(self, monkeypatch):
        captured = {}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            assert headers is None  # webhooks never send auth headers
            return _FakeWebhookResponse()

        monkeypatch.setattr("services.slack_service.requests.post", fake_post)
        service = SlackService(webhook_url="https://hooks.slack.com/services/T/B/X")
        assert service.send_notification("hello", thread_ts="172.1") is True
        assert captured["url"] == "https://hooks.slack.com/services/T/B/X"
        assert captured["json"] == {"text": "hello"}  # no thread key leaks in
        # Webhook roots still post top-level but yield no ts to store.
        assert service.post_thread_root(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="pending_review",
        ) is None

    def test_root_payload_carries_ref_risk_status(self):
        payload = SlackService().format_request_root_payload(
            request_ref="req-00007", requester="alice", risk_level="critical",
            request_text="read it", status="pending_review",
            duration_hours=2, environment="dev",
            grants_summary="1 action (s3:GetObject) on 1 resource (s3:example-bucket).",
        )
        header = payload["blocks"][0]["text"]["text"]
        assert header.startswith("🔎")
        assert "req-00007 - pending review" in header
        joined = str(payload["blocks"])
        assert "alice" in joined and "CRITICAL" in joined
        assert "*Requester*" in joined and "*Duration*" in joined
        assert "*What it grants*" in joined and "s3:GetObject" in joined
        assert "req-00007 - dev - IAM-Dynamic - updated " in joined


class TestTelegramThreading:
    def test_root_post_returns_message_id(self, monkeypatch):
        captured = {}
        _telegram_api(monkeypatch, captured)
        service = TelegramService(bot_token="t", chat_id="1")
        mid = service.post_thread_root(
            request_ref="req-00007", requester="alice", risk_level="high",
            request_text="read the bucket", status="pending_review",
        )
        assert mid == 42
        assert captured["json"]["chat_id"] == "1"
        assert captured["json"]["parse_mode"] == "HTML"
        assert "reply_to_message_id" not in captured["json"]
        assert "req-00007" in captured["json"]["text"]

    def test_reply_passes_reply_to_message_id(self, monkeypatch):
        captured = {}
        _telegram_api(monkeypatch, captured)
        service = TelegramService(bot_token="t", chat_id="1")
        assert service.send_decision_notification(
            request_ref="req-00007", decision="denied", reviewer="boss",
            requester="alice", risk_level="critical", request_text="x",
            feedback="nope", reply_to_message_id=42,
        ) is True
        assert captured["json"]["reply_to_message_id"] == 42

    def test_legacy_fake_without_json_still_reports_success(self, monkeypatch):
        def fake_post(url, json=None, timeout=None):
            return _FakeWebhookResponse()

        monkeypatch.setattr("services.telegram_service.requests.post", fake_post)
        service = TelegramService(bot_token="t", chat_id="1")
        assert service.send_message("hello") is True
        assert service.post_message("hello") is None

    def test_failure_returns_false_and_no_id(self, monkeypatch):
        import requests as requests_lib

        def fake_post(url, json=None, timeout=None):
            raise requests_lib.RequestException("boom")

        monkeypatch.setattr("services.telegram_service.requests.post", fake_post)
        service = TelegramService(bot_token="t", chat_id="1")
        assert service.send_message("hello") is False
        assert service.post_message("hello") is None

    def test_root_message_carries_ref_and_status(self):
        message = TelegramService(bot_token="t", chat_id="1").format_request_root_message(
            request_ref="req-00007", requester="alice", risk_level="low",
            request_text="read it", status="approved",
        )
        assert "req-00007" in message and "alice" in message
        assert "LOW" in message and "approved" in message


def _make_request_row(store, **overrides):
    kwargs = dict(
        requester="alice",
        request_text="read the example bucket",
        provider="muse",
        model="m",
        duration=2,
        policy=dict(SAFE_POLICY),
        risk="medium",
        explanation="",
        approver_note="",
        auto_approved=False,
        status="pending_review",
    )
    kwargs.update(overrides)
    return store.create(**kwargs)


class TestThreadRootStore:
    def test_fresh_db_has_null_roots(self, tmp_path):
        store = RequestStore(tmp_path / "fresh.db")
        row = _make_request_row(store)
        assert store.get_thread_roots(row["id"]) == {
            "slack_thread_ts": None,
            "telegram_root_message_id": None,
        }
        assert store.get_thread_roots(9999) is None
        store.close()

    def test_claim_once_second_loses(self, tmp_path):
        store = RequestStore(tmp_path / "claim.db")
        row = _make_request_row(store)
        assert store.claim_slack_thread(row["id"], "ts-1") is True
        assert store.claim_slack_thread(row["id"], "ts-2") is False
        assert store.claim_telegram_root(row["id"], 11) is True
        assert store.claim_telegram_root(row["id"], 22) is False
        assert store.get_thread_roots(row["id"]) == {
            "slack_thread_ts": "ts-1",
            "telegram_root_message_id": 11,
        }
        store.close()

    def test_concurrent_claims_elect_exactly_one_winner(self, tmp_path):
        store = RequestStore(tmp_path / "race.db")
        row = _make_request_row(store)
        wins = []
        lock = threading.Lock()

        def claim(i):
            won = store.claim_slack_thread(row["id"], f"ts-{i}")
            with lock:
                wins.append(won)

        threads = [threading.Thread(target=claim, args=(i,)) for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        assert wins.count(True) == 1
        store.close()

    def test_v3_database_migrates_to_v4(self, tmp_path):
        db = tmp_path / "v3.db"
        conn = sqlite3.connect(db)
        for script in rs_mod._MIGRATIONS[:3]:
            conn.executescript(script)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta"
            " (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute(
            "INSERT INTO schema_meta (key, value) VALUES ('version', '3')"
        )
        conn.execute(
            "INSERT INTO access_requests (requester, request_text, provider,"
            " duration, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("alice", "old request", "muse", 2,
             "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()

        store = RequestStore(db)
        rows = store.list()
        assert len(rows) == 1 and rows[0]["request_text"] == "old request"
        assert store.get_thread_roots(rows[0]["id"]) == {
            "slack_thread_ts": None,
            "telegram_root_message_id": None,
        }
        assert store.claim_slack_thread(rows[0]["id"], "ts-old") is True
        version = store._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()["value"]
        assert version == str(rs_mod.SCHEMA_VERSION)
        store.close()


class _StubPolicyProvider:
    def __init__(self, risk="medium"):
        self.risk = risk

    def generate_policy(self, request_text):
        from llm_service import PolicyResponse

        return [
            PolicyResponse(
                policy=dict(SAFE_POLICY),
                risk=self.risk,
                explanation="stub",
                approver_note="stub",
            )
        ]


class FakeSlack:
    """Recording stand-in; roots return a ts, None when unconfigured."""

    def __init__(self, configured=True):
        self.configured = configured
        self.roots = []
        self.decisions = []
        self.credentials = []
        self.notes = []

    def post_thread_root(self, **kwargs):
        self.roots.append(kwargs)
        if not self.configured:
            return None
        return f"ts-{len(self.roots)}"

    def send_decision_notification(self, **kwargs):
        self.decisions.append(kwargs)
        return True

    def send_credential_notification(self, **kwargs):
        self.credentials.append(kwargs)
        return True

    def send_notification(self, message, thread_ts=None):
        self.notes.append({"message": message, "thread_ts": thread_ts})
        return True


class FakeTelegram:
    def __init__(self, configured=True):
        self.configured = configured
        self.roots = []
        self.decisions = []
        self.credentials = []
        self.notes = []

    def post_thread_root(self, **kwargs):
        self.roots.append(kwargs)
        if not self.configured:
            return None
        return 100 + len(self.roots)

    def send_decision_notification(self, **kwargs):
        self.decisions.append(kwargs)
        return True

    def send_credential_notification(self, **kwargs):
        self.credentials.append(kwargs)
        return True

    def send_message(self, text, reply_to_message_id=None):
        self.notes.append({"text": text, "reply_to_message_id": reply_to_message_id})
        return True


@pytest.fixture()
def _as_user(monkeypatch):
    monkeypatch.setattr(main, "auth_service", None)
    monkeypatch.setattr(main, "_is_admin", lambda username: username == "boss")

    def use(username):
        main.app.dependency_overrides[main.get_current_user] = lambda: username

    yield use
    main.app.dependency_overrides.clear()


@pytest.fixture()
def _wired(monkeypatch):
    """Stub LLM/STS and install recording channel fakes (threading on)."""
    monkeypatch.setattr(
        main, "get_llm_provider", lambda *a, **k: _StubPolicyProvider()
    )
    slack, telegram = FakeSlack(), FakeTelegram()
    monkeypatch.setattr(main, "slack_service", slack)
    monkeypatch.setattr(main, "telegram_service", telegram)

    def fake_assume(policy, duration, role_arn=None):
        return {
            "AccessKeyId": "AKIA",
            "SecretAccessKey": "s",
            "SessionToken": "t",
            "Expiration": datetime.now(timezone.utc),
        }

    monkeypatch.setattr(main.sts_service, "assume_role_with_policy", fake_assume)
    return slack, telegram


def _body(**overrides):
    body = {
        "request_text": "I need to read objects from the example bucket for debugging.",
        "provider": "muse",
        "duration": 2,
    }
    body.update(overrides)
    return body


class TestThreadWiring:
    def test_submit_posts_one_root_per_request(self, _as_user, _wired):
        _as_user("alice")
        slack, telegram = _wired
        request_id = TestClient(main.app).post("/api/requests", json=_body()).json()[0]["id"]
        assert len(slack.roots) == 1 and len(telegram.roots) == 1
        assert slack.roots[0]["requester"] == "alice"
        assert main.get_request_store().get_thread_roots(request_id) == {
            "slack_thread_ts": "ts-1",
            "telegram_root_message_id": 101,
        }

    def test_decision_replies_without_new_root(self, _as_user, _wired):
        _as_user("alice")
        slack, telegram = _wired
        client = TestClient(main.app)
        request_id = client.post("/api/requests", json=_body()).json()[0]["id"]
        _as_user("boss")
        response = client.post(
            f"/api/requests/{request_id}/review",
            json={"decision": "approve"},
        )
        assert response.status_code == 200
        assert len(slack.roots) == 1  # no second root
        assert slack.decisions[0]["thread_ts"] == "ts-1"
        assert telegram.decisions[0]["reply_to_message_id"] == 101
        assert telegram.decisions[0]["reviewer"] == "boss"

    def test_lazy_root_on_review_for_pre_threading_request(self, _as_user, monkeypatch):
        monkeypatch.setattr(
            main, "get_llm_provider", lambda *a, **k: _StubPolicyProvider()
        )
        monkeypatch.setattr(main, "slack_service", FakeSlack(configured=False))
        monkeypatch.setattr(main, "telegram_service", FakeTelegram(configured=False))
        _as_user("alice")
        client = TestClient(main.app)
        request_id = client.post("/api/requests", json=_body()).json()[0]["id"]
        # Webhook-fallback roots store nothing.
        assert main.get_request_store().get_thread_roots(request_id) == {
            "slack_thread_ts": None,
            "telegram_root_message_id": None,
        }
        slack, telegram = FakeSlack(), FakeTelegram()
        monkeypatch.setattr(main, "slack_service", slack)
        monkeypatch.setattr(main, "telegram_service", telegram)
        _as_user("boss")
        assert client.post(
            f"/api/requests/{request_id}/review",
            json={"decision": "deny", "feedback": "too broad"},
        ).status_code == 200
        assert len(slack.roots) == 1 and len(telegram.roots) == 1
        assert slack.decisions[0]["thread_ts"] == "ts-1"
        assert telegram.decisions[0]["reply_to_message_id"] == 101

    def test_activation_issuance_threads(self, _as_user, _wired):
        _as_user("alice")
        slack, telegram = _wired
        client = TestClient(main.app)
        request_id = client.post("/api/requests", json=_body()).json()[0]["id"]
        _as_user("boss")
        client.post(f"/api/requests/{request_id}/review", json={"decision": "approve"})
        _as_user("alice")
        assert client.post(f"/api/requests/{request_id}/activate").status_code == 200
        assert len(slack.roots) == 1
        assert slack.credentials[0]["thread_ts"] == "ts-1"
        assert telegram.credentials[0]["reply_to_message_id"] == 101

    def test_resubmit_replies_in_thread(self, _as_user, _wired):
        _as_user("alice")
        slack, telegram = _wired
        client = TestClient(main.app)
        request_id = client.post("/api/requests", json=_body()).json()[0]["id"]
        _as_user("boss")
        client.post(
            f"/api/requests/{request_id}/review",
            json={"decision": "changes_requested", "feedback": "narrow it"},
        )
        _as_user("alice")
        response = client.post(
            f"/api/requests/{request_id}/resubmit",
            json={"request_text": "I need to read one object from the example bucket."},
        )
        assert response.status_code == 200
        assert len(slack.roots) == 1  # same thread, new revision
        assert slack.notes[0]["thread_ts"] == "ts-1"
        assert "revision 2" in slack.notes[0]["message"] and "alice" in slack.notes[0]["message"]
        assert telegram.notes[0]["reply_to_message_id"] == 101

    def test_webhook_fallback_never_threads(self, _as_user, monkeypatch):
        monkeypatch.setattr(
            main, "get_llm_provider", lambda *a, **k: _StubPolicyProvider()
        )
        slack, telegram = FakeSlack(configured=False), FakeTelegram(configured=False)
        monkeypatch.setattr(main, "slack_service", slack)
        monkeypatch.setattr(main, "telegram_service", telegram)
        _as_user("alice")
        client = TestClient(main.app)
        request_id = client.post("/api/requests", json=_body()).json()[0]["id"]
        _as_user("boss")
        client.post(f"/api/requests/{request_id}/review", json={"decision": "approve"})
        assert main.get_request_store().get_thread_roots(request_id) == {
            "slack_thread_ts": None,
            "telegram_root_message_id": None,
        }
        assert slack.decisions[0]["thread_ts"] is None
        assert telegram.decisions[0]["reply_to_message_id"] is None
