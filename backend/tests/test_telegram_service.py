"""Telegram notification service tests."""
from services.telegram_service import TelegramService
from config import TelegramConfig


class TestEnabledGating:
    def test_disabled_without_credentials(self):
        service = TelegramService()
        assert service.enabled is False
        assert service.send_message("hello") is False

    def test_disabled_with_token_only(self):
        assert TelegramService(bot_token="123:abc").enabled is False

    def test_disabled_with_chat_id_only(self):
        assert TelegramService(chat_id="12345").enabled is False

    def test_config_requires_both_values(self):
        assert TelegramConfig(bot_token="123:abc").enabled is False
        assert TelegramConfig(chat_id="42").enabled is False
        assert TelegramConfig(bot_token="123:abc", chat_id="42").enabled is True


class TestMessageFormatting:
    """Credential issuance is a terse two-line reply; the card root holds details."""

    def test_credential_reply_names_requester_and_expiry(self):
        service = TelegramService(bot_token="t", chat_id="1")
        message = service.format_credential_message(
            request_text="read logs",
            risk_level="low",
            duration_hours=12,
            auto_approved=True,
            requester="alice",
            expires_at="2026-11-01 16:10 UTC",
        )
        assert len(message.splitlines()) <= 3
        assert "alice" in message
        assert "2026-11-01 16:10 UTC" in message
        assert "Card above updated." in message
        assert message.startswith("🔓")

    def test_credential_reply_has_no_card_fields(self):
        service = TelegramService(bot_token="t", chat_id="1")
        message = service.format_credential_message(
            request_text="read logs",
            risk_level="low",
            duration_hours=12,
            auto_approved=True,
            requester="alice",
        )
        assert "Requested by" not in message
        assert "Risk Score" not in message
        assert "read logs" not in message

    def test_credential_reply_escapes_html(self):
        service = TelegramService(bot_token="t", chat_id="1")
        message = service.format_credential_message(
            request_text="read logs",
            risk_level="low",
            duration_hours=12,
            auto_approved=True,
            requester="<admin>",
        )
        # Raw HTML must never reach Telegram's HTML parser
        assert "<admin>" not in message
        assert "&lt;admin&gt;" in message


class TestSendMessage:
    def test_sends_to_bot_api_with_html_parse_mode(self, monkeypatch):
        captured = {}

        class FakeResponse:
            def raise_for_status(self):
                pass

        def fake_post(url, json=None, timeout=None):
            captured["url"] = url
            captured["json"] = json
            captured["timeout"] = timeout
            return FakeResponse()

        monkeypatch.setattr("services.telegram_service.requests.post", fake_post)
        service = TelegramService(bot_token="123:ABC", chat_id="98765")
        result = service.send_credential_notification(
            request_text="read bucket", risk_level="low",
            duration_hours=4, auto_approved=True,
            requester="alice", expires_at="2026-11-01 16:10 UTC",
        )

        assert result is True
        assert captured["url"] == "https://api.telegram.org/bot123:ABC/sendMessage"
        assert captured["json"]["chat_id"] == "98765"
        assert captured["json"]["parse_mode"] == "HTML"
        assert "alice" in captured["json"]["text"]
        assert "Card above updated." in captured["json"]["text"]

    def test_returns_false_on_http_error(self, monkeypatch):
        import requests as requests_lib

        def fake_post(url, json=None, timeout=None):
            raise requests_lib.RequestException("boom")

        monkeypatch.setattr("services.telegram_service.requests.post", fake_post)
        service = TelegramService(bot_token="123:ABC", chat_id="98765")
        assert service.send_message("hello") is False


class TestDecisionMessage:
    def _message(self, **overrides):
        kwargs = dict(
            request_ref="req-00007",
            decision="denied",
            reviewer="chad",
            requester="bob",
            risk_level="critical",
            request_text="read the production-logs bucket",
            feedback="too broad, narrow it",
        )
        kwargs.update(overrides)
        service = TelegramService(bot_token="t", chat_id="1")
        return service.format_decision_message(**kwargs)

    def test_denied_terse_reply(self):
        message = self._message()
        assert message.startswith("❌")
        assert "Denied" in message and "chad" in message
        assert "card above updated" in message
        assert len(message.splitlines()) <= 3

    def test_reply_has_no_card_fields(self):
        message = self._message()
        assert "Requested by" not in message
        assert "Risk Score" not in message
        assert "read the production-logs bucket" not in message

    def test_approved_and_sent_back_emoji(self):
        assert self._message(decision="approved").startswith("✅")
        assert self._message(decision="changes_requested").startswith("↩️")

    def test_feedback_omitted_when_absent(self):
        assert "blockquote" not in self._message(feedback=None)
        assert "too broad" in self._message()

    def test_user_content_is_html_escaped(self):
        message = self._message(request_text="<b>x</b>", reviewer="<i>chad</i>")
        assert "<i>chad</i>" not in message
        assert "&lt;i&gt;chad&lt;/i&gt;" in message
