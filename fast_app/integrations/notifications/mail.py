import base64
import json
import logging
import os
import smtplib
from email import encoders
from email.message import Message
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Optional
from urllib import error, request

import markdown
from pydantic import BaseModel, Field

from fast_app.utils.file_utils import get_mime_type


class MailAttachment(BaseModel):
    filename: str = Field(..., title="Attachment filename")
    content: bytes = Field(..., title="Attachment bytes")
    content_type: Optional[str] = Field(None, title="Attachment MIME type")

    @property
    def resolved_content_type(self) -> str:
        return self.content_type or get_mime_type(self.filename) or "application/octet-stream"

    def get_mime_part(self) -> MIMEBase:
        maintype, subtype = self.resolved_content_type.split("/", 1)
        part = MIMEBase(maintype, subtype)
        part.set_payload(self.content)
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=self.filename)
        return part

    def to_smtp2go_payload(self) -> dict[str, str]:
        return {
            "filename": self.filename,
            "mimetype": self.resolved_content_type,
            "fileblob": base64.b64encode(self.content).decode("ascii"),
        }


class MailMessage(BaseModel):
    subject: str = Field(..., title="Email subject")
    body: str = Field(..., title="Email body")
    mime_type: str = Field("plain", title="MIME type of the email body")
    attachments: list[MailAttachment] = Field(default_factory=list, title="Email attachments")

    def get_text_body(self) -> Optional[str]:
        return None if self.mime_type == "html" else self.body

    def get_html_body(self) -> Optional[str]:
        return self.body if self.mime_type == "html" else None

    def _get_body_part(self) -> Message:
        return MIMEText(self.body, self.mime_type)

    def get_mail(self) -> MIMEBase:
        body_part = self._get_body_part()

        if self.attachments:
            mail = MIMEMultipart("mixed")
            mail.attach(body_part)
            for attachment in self.attachments:
                mail.attach(attachment.get_mime_part())
        else:
            mail = body_part

        mail["Subject"] = self.subject
        mail["From"] = os.getenv("MAIL_FROM")

        return mail


class MarkdownMailMessage(MailMessage):
    def get_text_body(self) -> Optional[str]:
        return self.body

    def get_html_body(self) -> Optional[str]:
        return markdown.markdown(self.body)

    def _get_body_part(self) -> Message:
        mail = MIMEMultipart("alternative")
        mail.attach(MIMEText(self.body, "plain"))
        mail.attach(MIMEText(markdown.markdown(self.body), "html"))
        return mail


class Mail:
    @classmethod
    def send(cls, to: str, message: MailMessage):
        cls.__validate_attachments(message)
        mail_driver = os.getenv("MAIL_DRIVER", "log").lower()

        if mail_driver == "smtp":
            cls.__send_smtp(to, message)
        elif mail_driver == "smtp2go":
            cls.__send_smtp2go(to, message)
        elif mail_driver == "log":
            cls.__send_log(to, message)

    @classmethod
    def __send_smtp(cls, to: str, message: MailMessage):
        mail = message.get_mail()

        with smtplib.SMTP(os.getenv("MAIL_SERVER"), int(os.getenv("MAIL_PORT"))) as server:
            server.starttls()
            server.login(os.getenv("MAIL_LOGIN"), os.getenv("MAIL_PASSWORD"))
            server.sendmail(os.getenv("MAIL_FROM"), to, mail.as_string())

    @classmethod
    def __send_smtp2go(cls, to: str, message: MailMessage):
        smtp2go_api_key = os.getenv("SMTP2GO_API_KEY")
        if not smtp2go_api_key:
            raise ValueError("SMTP2GO_API_KEY is required when MAIL_DRIVER=smtp2go")

        payload = {
            "sender": os.getenv("MAIL_FROM"),
            "to": [to],
            "subject": message.subject,
        }

        text_body = message.get_text_body()
        html_body = message.get_html_body()

        if text_body is not None:
            payload["text_body"] = text_body
        if html_body is not None:
            payload["html_body"] = html_body
        if message.attachments:
            payload["attachments"] = [
                attachment.to_smtp2go_payload()
                for attachment in message.attachments
            ]

        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            url="https://api.smtp2go.com/v3/email/send",
            data=body,
            headers={
                "Content-Type": "application/json",
                "Accept": "application/json",
                "X-Smtp2go-Api-Key": smtp2go_api_key,
            },
            method="POST",
        )

        try:
            with request.urlopen(req) as response:
                response_data = json.loads(response.read().decode("utf-8"))
        except error.HTTPError as exc:
            response_body = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(
                f"SMTP2GO request failed with status {exc.code}: {response_body}"
            ) from exc
        except error.URLError as exc:
            raise RuntimeError(f"SMTP2GO request failed: {exc.reason}") from exc

        failed = response_data.get("data", {}).get("failed", 0)
        if failed:
            raise RuntimeError(f"SMTP2GO failed to deliver {failed} email(s)")

    @classmethod
    def __send_log(cls, to: str, message: MailMessage):
        attachment_names = ", ".join(
            attachment.filename for attachment in message.attachments
        ) or "none"
        msg = f"""[MAIL]
        To: {to}
        Subject: {message.subject}
        Attachments: {attachment_names}
        ======== BODY ========
        {message.body}
        """
        logging.info(msg)
        print(msg)

    @staticmethod
    def __validate_attachments(message: MailMessage) -> None:
        max_bytes_raw = os.getenv("MAIL_MAX_ATTACHMENT_BYTES")
        if not max_bytes_raw or not message.attachments:
            return

        try:
            max_bytes = int(max_bytes_raw)
        except ValueError as exc:
            raise ValueError("MAIL_MAX_ATTACHMENT_BYTES must be an integer") from exc

        total_bytes = sum(len(attachment.content) for attachment in message.attachments)
        if total_bytes > max_bytes:
            raise ValueError(
                "Total attachment size exceeds MAIL_MAX_ATTACHMENT_BYTES "
                f"({total_bytes} > {max_bytes})"
            )


def send_via_mail(to: str, subject: str, body: str):
    Mail.send(to, MarkdownMailMessage(subject=subject, body=body))
