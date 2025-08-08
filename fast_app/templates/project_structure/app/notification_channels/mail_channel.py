from typing import TYPE_CHECKING

from fast_app.notification_channel_base import NotificationChannel
from fast_app.common.mail import Mail

if TYPE_CHECKING:
    from app.models.user import User
    from fast_app.notification_base import Notification


class MailChannel(NotificationChannel):

    async def send(self, notifiable: 'User', notification: 'Notification'):
        if receiver_mail := notifiable.get("email"):
            Mail.send(receiver_mail, await notification.to_mail(notifiable))