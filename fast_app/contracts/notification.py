from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from fast_app.common.queue import queue

if TYPE_CHECKING:
    from fast_app.notification_channel_base import NotificationChannel
    from fast_app.model_base import Model


class Notification(ABC):

    def via(self, notifiable: 'Model') -> list['NotificationChannel']:
        return []

    async def send(self, notifiable: 'Model'):
        for channel in self.via(notifiable):
            queue(channel.send, notifiable, self)

