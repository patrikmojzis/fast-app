from typing import TYPE_CHECKING

from fast_app import NotificationChannel
from fast_app.integrations.notifications.mail import Mail

if TYPE_CHECKING:
    from app.models.user import User
    from fast_app import Notification


class MailChannel(NotificationChannel):

    async def send(self, notifiable: 'User', notification: 'Notification'):
        if receiver_mail := notifiable.get("email"):
            Mail.send(receiver_mail, await notification.to_mail(notifiable))
