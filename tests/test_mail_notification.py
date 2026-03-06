import base64
import json
from email import message_from_string

import pytest

from fast_app.integrations.notifications.mail import (
    Mail,
    MailAttachment,
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


def test_mail_message_with_attachment_builds_multipart_mime():
    message = MailMessage(
        subject="Invoice",
        body="Attached invoice.",
        attachments=[
            MailAttachment(
                filename="invoice.pdf",
                content=b"pdf-bytes",
                content_type="application/pdf",
            )
        ],
    )

    mail = message.get_mail()

    assert mail.get_content_type() == "multipart/mixed"
    parts = mail.get_payload()
    assert len(parts) == 2
    assert parts[0].get_content_type() == "text/plain"
    assert parts[0].get_payload(decode=True) == b"Attached invoice."
    assert parts[1].get_filename() == "invoice.pdf"
    assert parts[1].get_content_type() == "application/pdf"
    assert parts[1].get_payload(decode=True) == b"pdf-bytes"


def test_markdown_mail_message_with_attachment_keeps_alternative_body():
    message = MarkdownMailMessage(
        subject="Invoice",
        body="**hello**",
        attachments=[MailAttachment(filename="invoice.txt", content=b"hello")],
    )

    mail = message.get_mail()

    assert mail.get_content_type() == "multipart/mixed"
    parts = mail.get_payload()
    assert len(parts) == 2
    assert parts[0].get_content_type() == "multipart/alternative"
    alt_parts = parts[0].get_payload()
    assert [part.get_content_type() for part in alt_parts] == ["text/plain", "text/html"]
    assert alt_parts[0].get_payload(decode=True) == b"**hello**"
    assert b"<strong>hello</strong>" in alt_parts[1].get_payload(decode=True)


def test_send_smtp_includes_attachment_in_mime_message(monkeypatch):
    monkeypatch.setenv("MAIL_FROM", "sender@example.com")
    monkeypatch.setenv("MAIL_SERVER", "smtp.example.com")
    monkeypatch.setenv("MAIL_PORT", "587")
    monkeypatch.setenv("MAIL_LOGIN", "login")
    monkeypatch.setenv("MAIL_PASSWORD", "password")

    captured = {}

    class FakeSMTP:
        def __init__(self, host, port):
            captured["host"] = host
            captured["port"] = port

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_value, traceback):
            return False

        def starttls(self):
            captured["starttls"] = True

        def login(self, login, password):
            captured["login"] = (login, password)

        def sendmail(self, sender, recipient, raw_message):
            captured["sender"] = sender
            captured["recipient"] = recipient
            captured["raw_message"] = raw_message

    monkeypatch.setattr("fast_app.integrations.notifications.mail.smtplib.SMTP", FakeSMTP)

    Mail._Mail__send_smtp(
        "recipient@example.com",
        MailMessage(
            subject="Invoice",
            body="Attached invoice.",
            attachments=[MailAttachment(filename="invoice.pdf", content=b"pdf-bytes")],
        ),
    )

    parsed = message_from_string(captured["raw_message"])

    assert captured["host"] == "smtp.example.com"
    assert captured["port"] == 587
    assert captured["starttls"] is True
    assert captured["login"] == ("login", "password")
    assert captured["sender"] == "sender@example.com"
    assert captured["recipient"] == "recipient@example.com"
    assert parsed.get_content_type() == "multipart/mixed"
    assert parsed.get_payload()[1].get_filename() == "invoice.pdf"
    assert parsed.get_payload()[1].get_payload(decode=True) == b"pdf-bytes"


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

    message = MarkdownMailMessage(
        subject="Welcome",
        body="**hi**",
        attachments=[MailAttachment(filename="invoice.pdf", content=b"pdf-bytes")],
    )
    Mail._Mail__send_smtp2go("recipient@example.com", message)

    assert captured["url"] == "https://api.smtp2go.com/v3/email/send"
    assert captured["headers"]["x-smtp2go-api-key"] == "test-api-key"
    assert captured["payload"]["sender"] == "sender@example.com"
    assert captured["payload"]["to"] == ["recipient@example.com"]
    assert captured["payload"]["subject"] == "Welcome"
    assert captured["payload"]["text_body"] == "**hi**"
    assert captured["payload"]["html_body"] == "<p><strong>hi</strong></p>"
    assert captured["payload"]["attachments"] == [
        {
            "filename": "invoice.pdf",
            "mimetype": "application/pdf",
            "fileblob": base64.b64encode(b"pdf-bytes").decode("ascii"),
        }
    ]


def test_send_smtp2go_requires_api_key(monkeypatch):
    monkeypatch.delenv("SMTP2GO_API_KEY", raising=False)
    monkeypatch.setenv("MAIL_FROM", "sender@example.com")

    with pytest.raises(ValueError, match="SMTP2GO_API_KEY"):
        Mail._Mail__send_smtp2go(
            "recipient@example.com",
            MailMessage(subject="Subject", body="Body"),
        )


def test_mail_send_rejects_oversized_attachments(monkeypatch):
    monkeypatch.setenv("MAIL_DRIVER", "log")
    monkeypatch.setenv("MAIL_MAX_ATTACHMENT_BYTES", "4")

    with pytest.raises(ValueError, match="MAIL_MAX_ATTACHMENT_BYTES"):
        Mail.send(
            "recipient@example.com",
            MailMessage(
                subject="Invoice",
                body="Attached invoice.",
                attachments=[MailAttachment(filename="invoice.pdf", content=b"12345")],
            ),
        )
