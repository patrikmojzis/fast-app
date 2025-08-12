from typing import TYPE_CHECKING

from fast_app import NotificationChannel

if TYPE_CHECKING:
    from fast_app import Model, Notification


class NewClass(NotificationChannel):
    async def send(self, notifiable: 'Model', notification: 'Notification'):
        pass
