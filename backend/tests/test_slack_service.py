"""Slack notification service tests."""
from services.slack_service import SlackService


class TestEnabledGating:
    def test_disabled_without_webhook(self):
        service = SlackService()
        assert service.send_notification("hello") is False
        assert service.send_payload({"text": "hello"}) is False


class TestCredentialPayload:
    def _payload(self, **overrides):
        kwargs = dict(
            request_text="read the production-logs bucket",
            risk_level="high",
            duration_hours=2,
            auto_approved=False,
            approver="chad",
        )
        kwargs.update(overrides)
        return SlackService().format_credential_payload(**kwargs)

    def test_uses_block_kit_with_text_fallback(self):
        payload = self._payload()
        assert "blocks" in payload and "text" in payload
        types = [b["type"] for b in payload["blocks"]]
        assert types[0] == "header"
        assert "section" in types
        assert types[-1] == "context"  # timestamp footer

    def test_fields_carry_risk_duration_approval(self):
        payload = self._payload(risk_level="critical", duration_hours=1)
        joined = " ".join(
            f.get("text", "") for b in payload["blocks"] if b["type"] == "section"
            for f in b.get("fields", [])
        )
        assert "CRITICAL" in joined
        assert ":red_circle:" in joined
        assert "1 hour(s)" in joined
        assert "Manual — chad" in joined

    def test_auto_approved_variant(self):
        payload = self._payload(auto_approved=True)
        joined = " ".join(
            f.get("text", "") for b in payload["blocks"] if b["type"] == "section"
            for f in b.get("fields", [])
        )
        assert "Auto-approved" in joined

    def test_request_rendered_as_mrkdwn_blockquote(self):
        payload = self._payload(request_text="line one\nline two")
        sections = [b for b in payload["blocks"] if b["type"] == "section" and "text" in b]
        body = " ".join(s["text"]["text"] for s in sections)
        assert "> line one" in body and "> line two" in body

    def test_user_content_is_mrkdwn_escaped(self):
        """Link/mention/broadcast injection must be neutralized (Slack guidance)."""
        payload = self._payload(
            request_text="<http://phish.example|Approve here> & <!channel>",
            approver="<@U123>",
        )
        raw = str(payload)
        assert "<http://phish.example" not in raw
        assert "&lt;http://phish.example|Approve here&gt;" in raw
        assert "&amp; &lt;!channel&gt;" in raw
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
