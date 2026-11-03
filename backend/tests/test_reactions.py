"""Status reactions on the thread root post (Slack + Telegram)."""
from unittest.mock import MagicMock

import services.slack_service as slack_mod
import services.telegram_service as telegram_mod
from services.slack_service import SlackService
from services.telegram_service import TelegramService


def _ok_response(payload=None):
    resp = MagicMock()
    resp.raise_for_status.return_value = None
    resp.json.return_value = payload if payload is not None else {"ok": True}
    return resp


def test_slack_status_reaction_swaps_old_for_new(monkeypatch):
    calls = []

    def fake_post(url, json=None, headers=None, timeout=None):
        calls.append((url, json))
        return _ok_response()

    monkeypatch.setattr(slack_mod.requests, "post", fake_post)
    svc = SlackService(bot_token="xoxb-t", channel_id="C1")
    assert svc.set_status_reaction("123.45", "approved") is True
    add = [c for c in calls if c[0].endswith("reactions.add")]
    remove = [c for c in calls if c[0].endswith("reactions.remove")]
    assert add == [
        (
            slack_mod.SLACK_API_REACTIONS_ADD,
            {"channel": "C1", "timestamp": "123.45", "name": "white_check_mark"},
        )
    ]
    removed_names = {c[1]["name"] for c in remove}
    assert "white_check_mark" not in removed_names
    assert {"mag", "x", "unlock"} <= removed_names


def test_slack_status_reaction_noop_without_api(monkeypatch):
    monkeypatch.setattr(
        slack_mod.requests, "post", MagicMock(side_effect=AssertionError("no HTTP"))
    )
    assert SlackService(webhook_url="https://hooks/x").set_status_reaction("1.2", "denied") is False
    assert SlackService(bot_token="xoxb-t", channel_id="C1").set_status_reaction(None, "denied") is False


def test_telegram_status_reaction_sets_single_emoji(monkeypatch):
    calls = []

    def fake_post(url, json=None, timeout=None):
        calls.append((url, json))
        return _ok_response()

    monkeypatch.setattr(telegram_mod.requests, "post", fake_post)
    svc = TelegramService(bot_token="t", chat_id="42")
    assert svc.set_status_reaction(99, "waiting") is True
    assert calls == [
        (
            "https://api.telegram.org/bott/setMessageReaction",
            {"chat_id": "42", "message_id": 99, "reaction": [{"type": "emoji", "emoji": "⏳"}]},
        )
    ]


def test_telegram_error_logs_never_contain_bot_token(monkeypatch, caplog):
    # The Bot API URL embeds the token; a raw requests exception would
    # print it in full. Error logs must scrub it out.
    import logging

    def boom(url, json=None, timeout=None):
        raise telegram_mod.requests.RequestException(f"400 for url: {url}")

    monkeypatch.setattr(telegram_mod.requests, "post", boom)
    svc = TelegramService(bot_token="SECRET-TOKEN-123", chat_id="42")
    with caplog.at_level(logging.WARNING):
        assert svc.set_status_reaction(99, "approved") is False
    assert "SECRET-TOKEN-123" not in caplog.text
    assert "***" in caplog.text


def test_telegram_status_reaction_noop_unconfigured(monkeypatch):
    monkeypatch.setattr(
        telegram_mod.requests, "post", MagicMock(side_effect=AssertionError("no HTTP"))
    )
    assert TelegramService().set_status_reaction(1, "approved") is False
