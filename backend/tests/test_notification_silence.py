"""The suite must never post live notifications (51-orphan-post incident).

Two guards: conftest swaps main's live Slack/Telegram singletons for
unconfigured services on every test, and IAM_SILENCE_NOTIFICATIONS=1
silences the fan-out helpers for ad-hoc runs. Live posts happen only in
explicit notification-system tests run by hand.
"""
import main


def test_main_notification_services_are_unconfigured_in_tests():
    assert main.slack_service.api_enabled is False
    assert not main.slack_service.webhook_url
    assert main.telegram_service.enabled is False


class _Recorder:
    def __init__(self):
        self.calls = []

    def __getattr__(self, name):
        def record(*args, **kwargs):
            self.calls.append(name)
            return None

        return record


def test_silence_switch_blocks_decision_fanout(monkeypatch):
    slack, telegram = _Recorder(), _Recorder()
    monkeypatch.setattr(main, "slack_service", slack)
    monkeypatch.setattr(main, "telegram_service", telegram)
    monkeypatch.setenv("IAM_SILENCE_NOTIFICATIONS", "1")
    main.send_decision_notification(
        request_id=1,
        decision="denied",
        reviewer="boss",
        requester="alice",
        risk="high",
        req="delete everything",
        feedback="too broad",
    )
    assert slack.calls == []
    assert telegram.calls == []


def test_silence_switch_blocks_audit_fanout(monkeypatch):
    slack, telegram = _Recorder(), _Recorder()
    monkeypatch.setattr(main, "slack_service", slack)
    monkeypatch.setattr(main, "telegram_service", telegram)
    monkeypatch.setenv("IAM_SILENCE_NOTIFICATIONS", "1")
    main.send_audit_notification(
        auto_approved=False, req="list buckets", risk="low", duration=2
    )
    assert slack.calls == []
    assert telegram.calls == []
