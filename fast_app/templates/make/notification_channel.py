from fast_app.notification_channel_base import NotificationChannel
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app.model_base import Model
    from fast_app.notification_base import Notification


class NotificationChannel(NotificationChannel):
    
    async def send(self, notifiable: 'Model', notification: 'Notification'):
        pass