"""Pretty payloads, decision why, root emoji updates, stale sweep."""
from datetime import datetime, timedelta, timezone

import main
from services import request_store as rs_mod
from services.request_store import RequestStore
from services.slack_service import SlackService
from services.telegram_service import TelegramService
from services.decision_rationale import build_decision_rationale


def _stored(**overrides):
    row = dict(
        requester="alice",
        risk="medium",
        explanation="Allows reading the team bucket.",
        approver_note="Narrow to one bucket.",
        auto_approved=False,
        duration=2,
        environment="dev",
        narrative={"summary_plain": "You can read files in the team bucket."},
    )
    row.update(overrides)
    return row


class TestSlackPretty:
    def _card(self, **overrides):
        kwargs = dict(
            request_ref="req-00007",
            requester="alice",
            risk_level="high",
            request_text="read the bucket for CHG-1234",
            status="approved",
            environment="dev",
            duration_hours=2,
            decided_by="boss",
            decided_at="2026-11-01 14:10 UTC",
            why="alice is performing read-only tasks (s3:GetObject) against s3:team-bucket. Approved by boss for a short 2h window in dev. Based on work item CHG-1234.",
            feedback="scoped tightly, good",
            grants_summary="1 action (s3:GetObject) on 1 resource (s3:team-bucket).",
        )
        kwargs.update(overrides)
        return SlackService().format_request_root_payload(**kwargs)

    def test_card_block_order_header_divider_fields_request_grants_why_footer(self):
        payload = self._card()
        types = [b["type"] for b in payload["blocks"]]
        assert types[0] == "header"
        assert types[1] == "divider"
        assert types[2] == "section"  # paired fields row
        assert types[-1] == "context"
        body = str(payload["blocks"])
        assert "*What it grants*" in body
        assert "*Why*" in body
        assert "*Reviewer feedback*" in body
        assert "req-00007 - dev - IAM-Dynamic - updated " in body

    def test_card_fields_paired_and_short(self):
        # Native Block Kit fields (two per row in the channel; Slack
        # collapses them in the thread pane — accepted by the owner).
        payload = self._card()
        fields = payload["blocks"][2]["fields"]
        labels = [f["text"].split("\n")[0] for f in fields]
        assert labels == [
            "*Requester*", "*Risk*", "*Duration*",
            "*Environment*", "*Decided by*", "*When*",
        ]
        assert "🟢 dev" in fields[3]["text"]  # environment colour indicator
        for field in fields:
            assert len(field["text"]) < 120

    def test_decision_fields_only_after_decision(self):
        payload = self._card(decided_by=None, decided_at=None)
        labels = [f["text"].split("\n")[0] for f in payload["blocks"][2]["fields"]]
        assert "*Decided by*" not in labels

    def test_why_and_feedback_omitted_when_absent(self):
        payload = self._card(why=None, feedback=None, grants_summary=None)
        body = str(payload["blocks"])
        assert "*Why*" not in body
        assert "*Reviewer feedback*" not in body
        assert "*What it grants*" not in body

    def test_decision_reply_is_terse_single_section(self):
        payload = SlackService().format_decision_payload(
            request_ref="req-00007", decision="denied", reviewer="boss",
            requester="alice", risk_level="high", request_text="read the bucket",
            feedback="too broad",
        )
        assert len(payload["blocks"]) <= 2
        raw = str(payload["blocks"])
        assert "Requested by" not in raw
        assert "card above updated" in raw

    def test_quote_truncated_at_600_with_ellipsis(self):
        long_text = "x" * 900
        payload = SlackService().format_request_root_payload(
            request_ref="req-1", requester="a", risk_level="low",
            request_text=long_text, status="pending_review",
        )
        body = str(payload["blocks"])
        assert "x" * 900 not in body
        assert "…" in body

    def test_escaping_survives_pretty_layout(self):
        payload = self._card(
            request_text="<http://phish|x> & <!channel>", feedback="<@U1>"
        )
        raw = str(payload)
        assert "<http://phish" not in raw
        assert "&lt;http://phish|x&gt;" in raw

    def test_root_emoji_per_status(self):
        svc = SlackService()
        pending = svc.format_request_root_payload(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="pending_review",
        )
        approved = svc.format_request_root_payload(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="approved", environment="dev",
        )
        assert pending["blocks"][0]["text"]["text"].startswith("🔎")
        assert approved["blocks"][0]["text"]["text"].startswith("✅")
        assert "req-1 - dev - IAM-Dynamic - updated " in str(approved["blocks"][-1])

    def test_update_thread_root_body_has_channel_ts_blocks_no_thread_ts(self, monkeypatch):
        captured = {}

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"ok": True}

        def fake_post(url, json=None, timeout=None, headers=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

        monkeypatch.setattr("services.slack_service.requests.post", fake_post)
        svc = SlackService(bot_token="xoxb-t", channel_id="C1")
        assert svc.update_thread_root(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="activated", thread_ts="172.1",
            grants_summary="1 action (s3:GetObject) on 1 resource (s3:b).",
        ) is True
        assert captured["url"] == "https://slack.com/api/chat.update"
        assert captured["json"]["channel"] == "C1"
        assert captured["json"]["ts"] == "172.1"
        assert "thread_ts" not in captured["json"]
        assert "blocks" in captured["json"]
        assert captured["json"]["blocks"][0]["text"]["text"].startswith("🔓")
        assert "*What it grants*" in str(captured["json"]["blocks"])

    def test_update_thread_root_noop_without_api(self):
        assert SlackService().update_thread_root(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="approved", thread_ts="172.1",
        ) is False
        assert SlackService(webhook_url="https://hooks/x").update_thread_root(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="approved", thread_ts=None,
        ) is False


class TestTelegramPretty:
    def _svc(self):
        return TelegramService(bot_token="t", chat_id="1")

    def _card(self, **overrides):
        kwargs = dict(
            request_ref="req-00007",
            requester="alice",
            risk_level="critical",
            request_text="read it for CHG-1234",
            status="denied",
            environment="dev",
            duration_hours=2,
            decided_by="boss",
            decided_at="2026-11-01 14:10 UTC",
            why="alice is performing read-only tasks (s3:GetObject) against s3:team-bucket. Denied by boss for a short 2h window in dev.",
            feedback="too broad",
            grants_summary="1 action (s3:GetObject) on 1 resource (s3:team-bucket).",
        )
        kwargs.update(overrides)
        return self._svc().format_request_root_message(**kwargs)

    def test_card_hierarchy_separator_blockquote_footer(self):
        message = self._card()
        assert message.startswith("❌")
        assert "req-00007 - denied" in message
        assert "────────────────" in message
        assert "<b>Requester:</b> alice" in message
        assert "<b>What it grants:</b>" in message
        assert "<b>Why:</b>\n<pre>" in message
        assert "<b>Reviewer feedback:</b>" in message
        assert "<i>req-00007 - dev - IAM-Dynamic - updated " in message

    def test_decision_reply_is_terse(self):
        message = self._svc().format_decision_message(
            request_ref="req-00007", decision="denied", reviewer="boss",
            requester="alice", risk_level="critical", request_text="read it",
            feedback="too broad",
        )
        assert message.startswith("❌")
        assert len(message.splitlines()) <= 3
        assert "Requested by" not in message
        assert "card above updated" in message

    def test_long_section_uses_code_block(self):
        message = self._card(request_text="y\n" * 200)
        assert "<pre>" in message and "blockquote" not in message

    def test_short_section_uses_code_block(self):
        message = self._card(request_text="line one\nline two")
        assert "<pre>line one\nline two</pre>" in message

    def test_truncation_and_escaping(self):
        message = self._card(
            request_text="z" * 900, decided_by="<i>boss</i>",
        )
        assert "z" * 900 not in message
        assert "…" in message
        assert "&lt;i&gt;boss&lt;/i&gt;" in message

    def test_root_emoji_per_status(self):
        svc = self._svc()
        pending = svc.format_request_root_message(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="pending_review",
        )
        auto = svc.format_request_root_message(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="approved", environment="dev",
        )
        assert pending.startswith("🔎")
        assert auto.startswith("✅")
        assert "req-1 - dev - IAM-Dynamic - updated " in auto

    def test_update_thread_root_uses_edit_message_text(self, monkeypatch):
        captured = {}

        class FakeResponse:
            def raise_for_status(self):
                pass

            def json(self):
                return {"ok": True, "result": {"message_id": 7}}

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

        monkeypatch.setattr("services.telegram_service.requests.post", fake_post)
        assert self._svc().update_thread_root(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="discarded", message_id=7,
        ) is True
        assert captured["url"].endswith("/editMessageText")
        assert captured["json"]["message_id"] == 7
        assert captured["json"]["parse_mode"] == "HTML"
        assert captured["json"]["text"].startswith("🗑️")

    def test_update_thread_root_noop_when_unconfigured(self):
        assert TelegramService().update_thread_root(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="approved", message_id=7,
        ) is False
        assert self._svc().update_thread_root(
            request_ref="req-1", requester="a", risk_level="low",
            request_text="x", status="approved", message_id=None,
        ) is False


ADMIN_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["iam:CreateUser", "iam:AttachUserPolicy"],
            "Resource": ["*"],
        }
    ],
}

READ_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject", "s3:ListBucket"],
            "Resource": ["arn:aws:s3:::team-bucket"],
        }
    ],
}

WILDCARD_POLICY = {
    "Version": "2012-10-17",
    "Statement": [
        {
            "Effect": "Allow",
            "Action": ["s3:GetObject"],
            "Resource": ["arn:aws:s3:::team-bucket/*"],
        }
    ],
}


class TestDecisionRationale:
    def test_admin_level_with_resources_duration_and_ticket(self):
        why = build_decision_rationale(
            _stored(
                policy=dict(ADMIN_POLICY),
                request_text="Need IAM access for onboarding, see CHG-1234",
            ),
            "approved",
            "boss",
            "Scoped to a single role.",
        )
        assert "admin-level" in why
        assert "iam:CreateUser" in why
        assert "Approved by boss" in why
        assert "2h" in why and "dev" in why
        assert "CHG-1234" in why
        assert "Scoped to a single role." in why
        assert "Evaluation summary:" not in why
        assert len(why) <= 500

    def test_read_only_case(self):
        why = build_decision_rationale(
            _stored(policy=dict(READ_POLICY)), "approved", "boss", None
        )
        assert "read-only" in why
        assert "s3:GetObject" in why
        assert "s3:team-bucket" in why
        assert "Evaluation summary:" not in why

    def test_wildcard_resources_use_all_phrasing(self):
        why = build_decision_rationale(
            _stored(policy=dict(WILDCARD_POLICY)), "denied", "boss", "Too broad."
        )
        assert "all s3:team-bucket resources" in why
        assert "Denied by boss" in why
        assert "Evaluation summary:" not in why

    def test_no_ticket_means_no_work_item_text(self):
        why = build_decision_rationale(
            _stored(policy=dict(READ_POLICY), request_text="read the bucket please"),
            "approved",
            "boss",
            None,
        )
        assert "work item" not in why
        assert "Narrow to one bucket" in why  # evaluation context still grounds it

    def test_approval_without_feedback_or_ticket_still_reads_real(self):
        why = build_decision_rationale(
            _stored(policy=dict(READ_POLICY)), "approved", "boss", None
        )
        assert "Approved by boss" in why
        assert "Evaluation summary:" not in why
        assert "No evaluation summary recorded." not in why
        assert "Narrow to one bucket" in why

    def test_changes_requested_names_decision_and_feedback(self):
        why = build_decision_rationale(
            _stored(policy=dict(READ_POLICY)), "changes_requested", "boss", "Narrow it."
        )
        assert "Sent back for changes by boss" in why
        assert "Narrow it." in why

    def test_auto_approved_names_policy_rule(self):
        why = build_decision_rationale(
            _stored(auto_approved=True, risk="low", policy=dict(READ_POLICY)),
            "approved",
            "system",
            None,
        )
        assert "low risk auto-approved per policy" in why.lower()

    def test_empty_policy_never_invents_facts(self):
        why = build_decision_rationale(
            _stored(explanation="", approver_note="", narrative={}, policy={}),
            "approved",
            "boss",
            None,
        )
        assert "Evaluation summary:" not in why
        assert "work item" not in why
        assert len(why) <= 500

    def test_polish_fallback_on_provider_error(self, monkeypatch):
        def boom(*a, **k):
            raise RuntimeError("llm down")

        monkeypatch.setattr(main, "get_llm_provider", boom)
        why = main._build_why_for_decision(
            "denied", "boss", "alice", "high", "read it", "too broad",
            _stored(provider="muse"),
        )
        assert "too broad" in why  # deterministic text survives
        assert len(why) <= 500

    def test_polish_used_when_provider_succeeds(self, monkeypatch):
        class FakeProvider:
            def generate_decision_rationale(self, facts, decision):
                return "Polished: denied because too broad."

        monkeypatch.setattr(
            main, "get_llm_provider", lambda *a, **k: FakeProvider()
        )
        why = main._build_why_for_decision(
            "denied", "boss", "alice", "high", "read it", "too broad",
            _stored(provider="muse"),
        )
        assert why == "Polished: denied because too broad."

    def test_why_threaded_through_decision_payloads(self, monkeypatch):
        captured = {}

        class FakeSlack:
            def update_thread_root(self, **kwargs):
                return True

            def send_decision_notification(self, **kwargs):
                captured["slack"] = kwargs
                return True

        class FakeTelegram:
            def update_thread_root(self, **kwargs):
                return True

            def send_decision_notification(self, **kwargs):
                captured["telegram"] = kwargs
                return True

        monkeypatch.setattr(main, "slack_service", FakeSlack())
        monkeypatch.setattr(main, "telegram_service", FakeTelegram())
        monkeypatch.setattr(
            main, "get_llm_provider",
            lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no llm")),
        )
        store = main.get_request_store()
        row = store.create(
            requester="alice", request_text="read the example bucket",
            provider="muse", model="m", duration=2, policy={},
            risk="high", explanation="Broad read.", approver_note="",
            auto_approved=False, status="pending_review",
        )
        main.send_decision_notification(
            request_id=row["id"], decision="denied", reviewer="boss",
            requester="alice", risk="high", req="read the example bucket",
            feedback="too broad", stored=store.get(row["id"]),
        )
        assert "Why" in captured["slack"]["why"] or "why" in str(captured["slack"])
        assert captured["slack"]["why"] is not None
        assert "too broad" in captured["slack"]["why"]
        assert "too broad" in captured["telegram"]["why"]


class TestRootCardKwargs:
    def _row(self, **overrides):
        row = dict(
            id=7,
            requester="alice",
            request_text="read the team bucket",
            risk="low",
            duration=2,
            environment="dev",
            policy=dict(READ_POLICY),
            reviewer=None,
            feedback=None,
            updated_at="2026-11-01T14:10:00+00:00",
            auto_approved=False,
        )
        row.update(overrides)
        return row

    def test_pending_root_has_grants_but_no_decision(self):
        card = main._root_card_kwargs(self._row(), "pending_review")
        assert "s3:GetObject" in card["grants_summary"]
        assert card["why"] is None
        assert card["decided_by"] is None
        assert card["duration_hours"] == 2

    def test_auto_approved_root_born_with_why(self):
        card = main._root_card_kwargs(
            self._row(status="approved", auto_approved=True), "approved"
        )
        assert card["decided_by"] == "system (auto-approved)"
        assert card["decided_at"] == "2026-11-01 14:10 UTC · 09:10 EST"
        assert "auto-approved per policy" in card["why"].lower()
        assert "Evaluation summary:" not in card["why"]

    def test_decided_root_carries_reviewer_and_feedback(self):
        card = main._root_card_kwargs(
            self._row(reviewer="boss", feedback="too broad"), "denied"
        )
        assert card["decided_by"] == "boss"
        assert card["feedback"] == "too broad"
        assert "Denied by boss" in card["why"]

    def test_pinned_why_wins_over_deterministic(self):
        card = main._root_card_kwargs(
            self._row(reviewer="boss"), "approved", why="Pinned narrative."
        )
        assert card["why"] == "Pinned narrative."


class TestStaleSchema:
    def test_fresh_db_has_null_stale_notice(self, tmp_path):
        store = RequestStore(tmp_path / "s.db")
        row = store.create(
            requester="alice", request_text="read the example bucket",
            provider="muse", model="m", duration=2, policy={},
            risk="medium", explanation="", approver_note="",
            auto_approved=False, status="pending_review",
        )
        assert store.get(row["id"])["stale_notice_at"] is None
        store.close()

    def test_v4_database_migrates_to_v5(self, tmp_path):
        db = tmp_path / "v4.db"
        import sqlite3

        conn = sqlite3.connect(db)
        for script in rs_mod._MIGRATIONS[:4]:
            conn.executescript(script)
        conn.execute(
            "CREATE TABLE IF NOT EXISTS schema_meta"
            " (key TEXT PRIMARY KEY, value TEXT NOT NULL)"
        )
        conn.execute("INSERT INTO schema_meta (key, value) VALUES ('version', '4')")
        conn.execute(
            "INSERT INTO access_requests (requester, request_text, provider,"
            " duration, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
            ("alice", "old", "muse", 2,
             "2026-01-01T00:00:00+00:00", "2026-01-01T00:00:00+00:00"),
        )
        conn.commit()
        conn.close()
        store = RequestStore(db)
        assert store.get(store.list()[0]["id"])["stale_notice_at"] is None
        version = store._conn.execute(
            "SELECT value FROM schema_meta WHERE key = 'version'"
        ).fetchone()["value"]
        assert version == str(rs_mod.SCHEMA_VERSION)
        store.close()

    def test_stale_listing_and_guarded_claim(self, tmp_path):
        store = RequestStore(tmp_path / "c.db")
        old = (datetime.now(timezone.utc) - timedelta(hours=3)).isoformat()
        row = store.create(
            requester="alice", request_text="read the example bucket",
            provider="muse", model="m", duration=2, policy={},
            risk="medium", explanation="", approver_note="",
            auto_approved=False, status="pending_review",
        )
        store._conn.execute(
            "UPDATE access_requests SET created_at = ? WHERE id = ?",
            (old, row["id"]),
        )
        store._conn.commit()
        cutoff = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
        assert [r["id"] for r in store.list_stale_pending(cutoff)] == [row["id"]]
        assert store.mark_stale_noticed(row["id"]) is True
        assert store.mark_stale_noticed(row["id"]) is False  # claimed once
        assert store.list_stale_pending(cutoff) == []
        store.close()


class _RootSpy:
    def __init__(self):
        self.roots = []
        self.notes = []
        self.updates = []

    def post_thread_root(self, **kwargs):
        self.roots.append(kwargs)
        return "ts-9"

    def update_thread_root(self, **kwargs):
        self.updates.append(kwargs)
        return True

    def send_notification(self, message, thread_ts=None):
        self.notes.append({"message": message, "thread_ts": thread_ts})
        return True

    def send_decision_notification(self, **kwargs):
        return True

    def send_credential_notification(self, **kwargs):
        return True


class _TGSpy:
    def __init__(self):
        self.roots = []
        self.notes = []
        self.updates = []

    def post_thread_root(self, **kwargs):
        self.roots.append(kwargs)
        return 99

    def update_thread_root(self, **kwargs):
        self.updates.append(kwargs)
        return True

    def send_message(self, text, reply_to_message_id=None):
        self.notes.append({"text": text, "reply_to_message_id": reply_to_message_id})
        return True

    def send_decision_notification(self, **kwargs):
        return True

    def send_credential_notification(self, **kwargs):
        return True


class TestStaleSweep:
    def _backdate(self, store, row_id, hours):
        old = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
        store._conn.execute(
            "UPDATE access_requests SET created_at = ? WHERE id = ?",
            (old, row_id),
        )
        store._conn.commit()

    def test_not_stale_untouched(self, monkeypatch):
        slack, telegram = _RootSpy(), _TGSpy()
        monkeypatch.setattr(main, "slack_service", slack)
        monkeypatch.setattr(main, "telegram_service", telegram)
        store = main.get_request_store()
        row = store.create(
            requester="alice", request_text="read the example bucket",
            provider="muse", model="m", duration=2, policy={},
            risk="medium", explanation="", approver_note="",
            auto_approved=False, status="pending_review",
        )
        assert main.check_stale_reviews() == 0
        assert slack.notes == [] and telegram.notes == []
        assert slack.updates == [] and telegram.updates == []
        assert store.get(row["id"])["stale_notice_at"] is None

    def test_stale_without_root_creates_root_and_threads_notice(self, monkeypatch):
        # Regression: a pre-threading request has no stored root. The
        # sweep must lazily create the root and thread the notice under
        # it — never post a stray top-level waiting message.
        slack, telegram = _RootSpy(), _TGSpy()
        monkeypatch.setattr(main, "slack_service", slack)
        monkeypatch.setattr(main, "telegram_service", telegram)
        store = main.get_request_store()
        row = store.create(
            requester="alice", request_text="read the example bucket",
            provider="muse", model="m", duration=2, policy={},
            risk="medium", explanation="", approver_note="",
            auto_approved=False, status="pending_review",
        )
        assert store.get_thread_roots(row["id"]) == {
            "slack_thread_ts": None, "telegram_root_message_id": None,
        }
        self._backdate(store, row["id"], hours=3)
        assert main.check_stale_reviews() == 1
        assert len(slack.roots) == 1 and len(telegram.roots) == 1
        assert slack.notes[0]["thread_ts"] == "ts-9"
        assert telegram.notes[0]["reply_to_message_id"] == 99
        roots = store.get_thread_roots(row["id"])
        assert roots["slack_thread_ts"] == "ts-9"
        assert roots["telegram_root_message_id"] == 99

    def test_stale_reminder_is_a_known_audit_event(self, tmp_path):
        from services.audit_log import AuditLog

        log = AuditLog(tmp_path / "audit.jsonl")
        entry = log.append(
            "stale_reminder", request_id=1, actor="system", actor_role="automated"
        )
        assert entry["event"] == "stale_reminder"

    def test_stale_claimed_once_second_run_quiet(self, monkeypatch):
        slack, telegram = _RootSpy(), _TGSpy()
        monkeypatch.setattr(main, "slack_service", slack)
        monkeypatch.setattr(main, "telegram_service", telegram)
        store = main.get_request_store()
        row = store.create(
            requester="alice", request_text="read the example bucket",
            provider="muse", model="m", duration=2, policy={},
            risk="medium", explanation="", approver_note="",
            auto_approved=False, status="pending_review",
        )
        store.claim_slack_thread(row["id"], "ts-9")
        store.claim_telegram_root(row["id"], 99)
        self._backdate(store, row["id"], hours=3)
        assert main.check_stale_reviews() == 1
        assert main.check_stale_reviews() == 0  # exactly once
        assert len(slack.notes) == 1 and len(telegram.notes) == 1
        assert "Waiting for review" in slack.notes[0]["message"]
        assert slack.notes[0]["thread_ts"] == "ts-9"
        assert telegram.notes[0]["reply_to_message_id"] == 99
        # Root emoji flipped to waiting on both channels.
        assert slack.updates[0]["status"] == "waiting"
        assert telegram.updates[0]["status"] == "waiting"
        assert store.get(row["id"])["stale_notice_at"] is not None
