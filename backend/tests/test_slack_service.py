"""Slack notification service tests."""
from services.slack_service import SlackService


class TestEnabledGating:
    def test_disabled_without_webhook(self):
        service = SlackService()
        assert service.send_notification("hello") is False
        assert service.send_payload({"text": "hello"}) is False


class TestCredentialPayload:
    """Credential issuance is a terse event-log reply; the card root holds details."""

    def _payload(self, **overrides):
        kwargs = dict(
            request_text="read the production-logs bucket",
            risk_level="high",
            duration_hours=2,
            auto_approved=False,
            approver="chad",
            requester="alice",
            expires_at="2026-11-01 16:10 UTC",
        )
        kwargs.update(overrides)
        return SlackService().format_credential_payload(**kwargs)

    def test_terse_single_section_with_text_fallback(self):
        payload = self._payload()
        assert "blocks" in payload and "text" in payload
        assert len(payload["blocks"]) <= 2
        assert payload["blocks"][0]["type"] == "section"

    def test_names_requester_expiry_and_card_pointer(self):
        payload = self._payload()
        body = payload["blocks"][0]["text"]["text"]
        assert "alice" in body
        assert "2026-11-01 16:10 UTC" in body
        assert "card above updated" in body
        assert "🔓" in body

    def test_no_repeated_card_fields(self):
        payload = self._payload()
        raw = str(payload["blocks"])
        assert "Requested by" not in raw
        assert "Risk Score" not in raw
        assert "🔓 AWS Temporary Credentials Issued" not in raw

    def test_user_content_is_mrkdwn_escaped(self):
        """Mention injection in the requester name must be neutralized."""
        payload = self._payload(requester="<@U123>")
        raw = str(payload)
        assert "<@U123>" not in raw
        assert "&lt;@U123&gt;" in raw


class TestSendPayload:
    def test_posts_payload_to_webhook(self, monkeypatch):
        captured = {}

        class FakeResponse:
            def raise_for_status(self):
                pass

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            return FakeResponse()

        monkeypatch.setattr("services.slack_service.requests.post", fake_post)
        service = SlackService(webhook_url="https://hooks.slack.com/services/T/B/X")
        assert service.send_credential_notification(
            request_text="read bucket", risk_level="low",
            duration_hours=4, auto_approved=True,
        ) is True
        assert captured["url"] == "https://hooks.slack.com/services/T/B/X"
        assert "blocks" in captured["json"]

    def test_returns_false_on_http_error(self, monkeypatch):
        import requests as requests_lib

        def fake_post(url, json=None, timeout=None):
            raise requests_lib.RequestException("boom")

        monkeypatch.setattr("services.slack_service.requests.post", fake_post)
        service = SlackService(webhook_url="https://hooks.slack.com/services/T/B/X")
        assert service.send_notification("hello") is False


class TestDecisionPayload:
    def _payload(self, **overrides):
        kwargs = dict(
            request_ref="req-00007",
            decision="approved",
            reviewer="chad",
            requester="bob",
            risk_level="high",
            request_text="read the production-logs bucket",
        )
        kwargs.update(overrides)
        return SlackService().format_decision_payload(**kwargs)

    def test_terse_reply_carries_decision_emoji_and_reviewer(self):
        payload = self._payload()
        assert len(payload["blocks"]) <= 2
        body = payload["blocks"][0]["text"]["text"]
        assert "Approved" in body
        assert "✅" in body
        assert "chad" in body
        assert "card above updated" in body

    def test_denied_and_sent_back_emoji(self):
        assert "❌" in self._payload(decision="denied")["blocks"][0]["text"]["text"]
        assert "↩️" in self._payload(decision="changes_requested")["blocks"][0]["text"]["text"]

    def test_no_repeated_card_fields(self):
        payload = self._payload()
        raw = str(payload["blocks"])
        assert "Requested by" not in raw
        assert "Risk Score" not in raw
        assert "read the production-logs bucket" not in raw

    def test_feedback_appended_short_only_when_present(self):
        no_fb = self._payload()["blocks"][0]["text"]["text"]
        assert ">" not in no_fb
        with_fb = self._payload(decision="denied", feedback="too broad, narrow it")
        assert "too broad, narrow it" in with_fb["blocks"][0]["text"]["text"]
        long_fb = self._payload(feedback="x" * 900)
        body = long_fb["blocks"][0]["text"]["text"]
        assert "x" * 900 not in body
        assert "…" in body

    def test_fallback_text_names_decision_and_reviewer(self):
        payload = self._payload(decision="denied", feedback="nope")
        assert "req-00007" in payload["text"]
        assert "denied" in payload["text"]
        assert "chad" in payload["text"]
