import os
from typing import TYPE_CHECKING

from fast_app import NotificationChannel
from fast_app.integrations.notification_channels.telegram import send_via_telegram

if TYPE_CHECKING:
    from app.models.user import User
    from fast_app import Notification


class TelegramChannel(NotificationChannel):
    async def send(self, notifiable: 'User', notification: 'Notification'):
        if chat_id := notifiable.get("telegram_user_id"):
            await send_via_telegram(
                await notification.to_telegram(notifiable),
                os.getenv('TELEGRAM_BOT_TOKEN'),
                chat_id
                ) 

