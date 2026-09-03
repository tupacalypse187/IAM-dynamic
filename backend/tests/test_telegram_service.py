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
    def test_credential_message_escapes_html(self):
        service = TelegramService(bot_token="t", chat_id="1")
        message = service.format_credential_message(
            request_text='read <b>s3</b> & "secret-bucket"',
            risk_level="high",
            duration_hours=2,
            auto_approved=False,
            approver="<admin>",
        )
        # Raw HTML must never reach Telegram's HTML parser
        assert "<b>s3</b>" not in message.replace("<b>AWS", "").replace("</b>", "")
        assert "&lt;b&gt;s3&lt;/b&gt;" in message
        assert "&amp;" in message
        assert "&lt;admin&gt;" in message
        assert "Manual" in message
        assert "HIGH" in message
        assert "2 hour(s)" in message

    def test_request_rendered_as_blockquote(self):
        service = TelegramService(bot_token="t", chat_id="1")
        message = service.format_credential_message(
            request_text="line one\nline two",
            risk_level="low",
            duration_hours=12,
            auto_approved=True,
        )
        assert "<blockquote>line one\nline two</blockquote>" in message

    def test_auto_approved_message(self):
        service = TelegramService(bot_token="t", chat_id="1")
        message = service.format_credential_message(
            request_text="read logs",
            risk_level="low",
            duration_hours=12,
            auto_approved=True,
        )
        assert "Auto-approved" in message
        assert "LOW" in message
        assert "🟢" in message  # risk emoji for low


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
        )

        assert result is True
        assert captured["url"] == "https://api.telegram.org/bot123:ABC/sendMessage"
        assert captured["json"]["chat_id"] == "98765"
        assert captured["json"]["parse_mode"] == "HTML"
        assert "read bucket" in captured["json"]["text"]

    def test_returns_false_on_http_error(self, monkeypatch):
        import requests as requests_lib

        def fake_post(url, json=None, timeout=None):
            raise requests_lib.RequestException("boom")

        monkeypatch.setattr("services.telegram_service.requests.post", fake_post)
        service = TelegramService(bot_token="123:ABC", chat_id="98765")
        assert service.send_message("hello") is False
