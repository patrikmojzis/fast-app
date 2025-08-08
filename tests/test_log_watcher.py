import os
import sys
import types
import pytest


@pytest.mark.asyncio
async def test_send_log_errors_via_slack(monkeypatch):
    os.environ["SEND_LOG_ERRORS_SLACK_WEBHOOK_URL"] = "http://example.com"
    os.environ["ENV"] = "test"

    stub_slack = types.SimpleNamespace(send_via_slack=lambda payload, url: None)
    sys.modules.setdefault(
        "fast_app.integrations.notification_channels.slack", stub_slack
    )
    sys.modules.setdefault(
        "fast_app.integrations.notification_channels.mail",
        types.SimpleNamespace(
            send_via_mail=None,
            MailMessage=object,
            MarkdownMailMessage=object,
            Mail=object,
        ),
    )
    sys.modules.setdefault(
        "fast_app.integrations.notification_channels.telegram",
        types.SimpleNamespace(send_via_telegram=None),
    )
    sys.modules.setdefault(
        "fast_app.integrations.notification_channels.expo",
        types.SimpleNamespace(send_via_push_notification=None),
    )
    import importlib
    module = importlib.import_module("fast_app.integrations.log_watcher.log_watcher_slack")
    send_log_errors_via_slack = module.send_log_errors_via_slack

    fake_errors = [{"level": "ERROR", "timestamp": "t", "logger": "root", "message": "m", "traceback": "tb"}]

    class FakeChecker:
        def __init__(self, check_minutes):
            pass
        def get_error_entries(self):
            return fake_errors

    monkeypatch.setattr(module, "LogErrorsChecker", FakeChecker)

    captured = {}

    async def fake_send(payload, url):
        captured["payload"] = payload
        captured["url"] = url

    monkeypatch.setattr(module, "send_via_slack", fake_send)

    await send_log_errors_via_slack()
    assert captured["url"] == "http://example.com"
    assert "ERROR Alert" in captured["payload"]["text"]
