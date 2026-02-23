import json

import pytest

from fast_app.integrations.notifications.mail import (
    Mail,
    MailMessage,
    MarkdownMailMessage,
)


def test_mail_send_dispatches_smtp2go_driver(monkeypatch):
    monkeypatch.setenv("MAIL_DRIVER", "smtp2go")

    captured = {}

    def fake_send_smtp2go(to, message):
        captured["to"] = to
        captured["message"] = message

    monkeypatch.setattr(Mail, "_Mail__send_smtp2go", fake_send_smtp2go)

    message = MailMessage(subject="Subject", body="Body")
    Mail.send("recipient@example.com", message)

    assert captured["to"] == "recipient@example.com"
    assert captured["message"] is message


def test_send_smtp2go_builds_expected_request(monkeypatch):
    monkeypatch.setenv("SMTP2GO_API_KEY", "test-api-key")
    monkeypatch.setenv("MAIL_FROM", "sender@example.com")

    captured = {}

    class FakeResponse:
        status = 200

        def read(self):
            return b'{"data": {"succeeded": 1, "failed": 0}}'

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

    def fake_urlopen(req):
        captured["url"] = req.full_url
        captured["headers"] = {k.lower(): v for k, v in req.header_items()}
        captured["payload"] = json.loads(req.data.decode("utf-8"))
        return FakeResponse()

    from fast_app.integrations.notifications import mail as mail_module

    monkeypatch.setattr(mail_module.request, "urlopen", fake_urlopen)

    message = MarkdownMailMessage(subject="Welcome", body="**hi**")
    Mail._Mail__send_smtp2go("recipient@example.com", message)

    assert captured["url"] == "https://api.smtp2go.com/v3/email/send"
    assert captured["headers"]["x-smtp2go-api-key"] == "test-api-key"
    assert captured["payload"]["sender"] == "sender@example.com"
    assert captured["payload"]["to"] == ["recipient@example.com"]
    assert captured["payload"]["subject"] == "Welcome"
    assert captured["payload"]["text_body"] == "**hi**"
    assert captured["payload"]["html_body"] == "<p><strong>hi</strong></p>"


def test_send_smtp2go_requires_api_key(monkeypatch):
    monkeypatch.delenv("SMTP2GO_API_KEY", raising=False)
    monkeypatch.setenv("MAIL_FROM", "sender@example.com")

    with pytest.raises(ValueError, match="SMTP2GO_API_KEY"):
        Mail._Mail__send_smtp2go(
            "recipient@example.com",
            MailMessage(subject="Subject", body="Body"),
        )
