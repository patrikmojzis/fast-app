# Notifications

Notifications provide a unified interface for sending messages across multiple channels—email, SMS, push notifications, Slack, etc. Define notification classes with channel-specific formatting and let the framework handle delivery via the queue.

## Making models notifiable

Models that receive notifications need the `@notifiable` decorator:

```python
from fast_app import Model
from fast_app.decorators.model_decorators import notifiable


@notifiable
class User(Model):
    name: str
    email: str | None = None
    phone: str | None = None
```

The decorator adds notification helpers to the model (currently just marks it as notifiable; channels determine routing logic).

## Generating notifications and channels

Use the CLI to scaffold notification and channel classes:

```bash
fast-app make notification EmailOTP
fast-app make notification_channel MailChannel
```

Notifications go to `app/notifications/`, channels to `app/notification_channels/`.

For common channels (mail, Telegram), publish pre-built templates:

```bash
fast-app publish mail_notification_channel
fast-app publish telegram_notification_channel
```

## Creating a notification

Notifications extend `fast_app.contracts.notification.Notification` and define:

- `via(notifiable)` — returns a list of channel instances
- Channel-specific methods like `to_mail(notifiable)`, `to_sms(notifiable)`, etc.

```python
from typing import TYPE_CHECKING

from fast_app import Notification
from fast_app.integrations.notifications.mail import MailMessage
from app.notification_channels.mail_channel import MailChannel

if TYPE_CHECKING:
    from fast_app import Model, NotificationChannel
    from app.models.email_otp import EmailOTP


class EmailOTPNotification(Notification):
    def __init__(self, email_otp: "EmailOTP"):
        self.email_otp = email_otp

    def via(self, notifiable: "Model") -> list["NotificationChannel"]:
        return [MailChannel()]

    async def to_mail(self, notifiable: "Model") -> MailMessage:
        otp = str(self.email_otp.otp)
        otp = otp[:3] + "-" + otp[3:] if len(otp) > 3 else otp

        return MailMessage(
            subject=f"🔑 {otp} is your verification code",
            body=f"Your code: {otp}. Expires in 15 minutes.",
        )
```

The notification class holds state (e.g., `email_otp`) and transforms it into channel-specific payloads.

## Creating a channel

Channels extend `fast_app.contracts.notification_channel.NotificationChannel` and implement `send(notifiable, notification)`:

```python
from typing import TYPE_CHECKING

from fast_app import NotificationChannel
from fast_app.integrations.notifications.mail import Mail

if TYPE_CHECKING:
    from app.models.user import User
    from fast_app import Notification


class MailChannel(NotificationChannel):
    async def send(self, notifiable: "User", notification: "Notification"):
        if receiver_mail := notifiable.get("email"):
            await Mail.send(receiver_mail, await notification.to_mail(notifiable))
```

Channels:
1. Extract recipient details from the `notifiable` model (e.g., `user.email`)
2. Call the notification's channel-specific method (`to_mail`)
3. Send via the integration (e.g., `Mail.send`)

## Sending notifications

Call `await notification.send(notifiable)` from anywhere in your application:

```python
from app.notifications.email_otp_notification import EmailOTPNotification

otp = await EmailOTP.create({"user_id": user.id, "otp": "123456"})
await EmailOTPNotification(otp).send(user)
```

Under the hood, `send()`:
1. Calls `via(notifiable)` to get channels
2. Enqueues `channel.send(notifiable, self)` for each channel via `fast_app.core.queue.queue`
3. Workers process deliveries asynchronously (when `QUEUE_DRIVER=async_farm`)

## Built-in integrations

FastApp ships with helpers for common channels:

### Mail

```python
from fast_app.integrations.notifications.mail import Mail, MailMessage

message = MailMessage(
    subject="Welcome!",
    body="Thanks for signing up.",
    html="<p>Thanks for signing up.</p>",
)
await Mail.send("user@example.com", message)
```

Configure via environment variables: `MAIL_HOST`, `MAIL_PORT`, `MAIL_USERNAME`, `MAIL_PASSWORD`, `MAIL_FROM`.

### Expo Push Notifications

```python
from fast_app.integrations.notifications.expo import Expo

await Expo.send_push_notification(
    tokens=["ExponentPushToken[...]"],
    title="New message",
    body="You have a new chat message",
)
```

Requires `EXPO_ACCESS_TOKEN`.

### Slack

```python
from fast_app.integrations.notifications.slack import Slack

await Slack.send_message(
    channel="#alerts",
    text="Deployment completed successfully",
)
```

Configure via `SLACK_WEBHOOK_URL`.

## Custom channels

Create a custom channel for any service:

```python
from fast_app import NotificationChannel


class SMSChannel(NotificationChannel):
    async def send(self, notifiable, notification):
        phone = notifiable.get("phone")
        message = await notification.to_sms(notifiable)
        await twilio_client.messages.create(to=phone, body=message)
```

Add a `to_sms()` method to your notifications:

```python
class EmailOTPNotification(Notification):
    def via(self, notifiable):
        channels = [MailChannel()]
        if notifiable.get("phone"):
            channels.append(SMSChannel())
        return channels

    async def to_sms(self, notifiable):
        return f"Your verification code: {self.email_otp.otp}"
```

## Tips

- Use `via(notifiable)` to conditionally select channels based on user preferences or availability (e.g., only send SMS if phone is present).
- Keep notification classes stateless except for the data they carry; channels handle delivery logic.
- Test notifications by calling `notification.to_mail(user)` directly without invoking `send()`.
- Combine with events: dispatch an event that triggers a listener which sends a notification.

Notifications centralize message formatting and delivery, making it easy to support new channels or update content without touching controllers.

