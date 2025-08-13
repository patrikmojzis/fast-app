import logging
import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import TYPE_CHECKING

import markdown
from pydantic import BaseModel, Field

if TYPE_CHECKING:
    from email.mime.base import MIMEBase

class MailMessage(BaseModel):
    subject: str = Field(..., title="Email subject")
    body: str = Field(..., title="Email body")
    mime_type: str = Field("plain", title="MIME type of the email body")

    def get_mail(self) -> 'MIMEBase':
        mail = MIMEText(self.body, self.mime_type)
        mail["Subject"] = self.subject
        mail["From"] = os.getenv("MAIL_FROM")

        return mail

class MarkdownMailMessage(MailMessage):
    def get_mail(self) -> 'MIMEBase':
        # Convert Markdown to HTML
        html_content = markdown.markdown(self.body)

        # Create the email
        mail = MIMEMultipart('alternative')
        mail['Subject'] = self.subject
        mail['From'] = os.getenv("MAIL_FROM")

        # Attach both plain text and HTML parts
        part1 = MIMEText(self.body, 'plain')
        part2 = MIMEText(html_content, 'html')

        mail.attach(part1)
        mail.attach(part2)

        return mail

class Mail:
    @classmethod
    def send(cls, to: str, message: 'MailMessage'):
        mail_driver = os.getenv("MAIL_DRIVER", "log").lower()

        if mail_driver == "smtp":
            cls.__send_smtp(to, message)
        elif mail_driver == "log":
            cls.__send_log(to, message)

    @classmethod
    def __send_smtp(cls, to: str, message: 'MailMessage'):
        mail = message.get_mail()

        with smtplib.SMTP(os.getenv("MAIL_SERVER"), int(os.getenv("MAIL_PORT"))) as server:
            server.starttls()
            server.login(os.getenv("MAIL_LOGIN"), os.getenv("MAIL_PASSWORD"))
            server.sendmail(os.getenv("MAIL_FROM"), to, mail.as_string())

    @classmethod
    def __send_log(cls, to: str, message: 'MailMessage'):
        msg = f"""[MAIL]
        To: {to}
        Subject: {message.subject}
        ======== BODY ========
        {message.body}
        """
        logging.info(msg)
        print(msg)


def send_via_mail(to: str, subject: str, body: str):
    Mail.send(to, MarkdownMailMessage(subject=subject, body=body))