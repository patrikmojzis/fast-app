from abc import ABC
from typing import TYPE_CHECKING

from fast_app.core.queue import queue

if TYPE_CHECKING:
    from fast_app import Model, NotificationChannel


class Notification(ABC):

    def via(self, notifiable: 'Model') -> list['NotificationChannel']:
        return []

    async def send(self, notifiable: 'Model'):
        for channel in self.via(notifiable):
            await queue(channel.send, notifiable, self)


