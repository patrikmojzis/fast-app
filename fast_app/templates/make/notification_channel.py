from fast_app import NotificationChannel
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app import Model, Notification


class NotificationChannel(NotificationChannel):
    
    async def send(self, notifiable: 'Model', notification: 'Notification'):
        pass
