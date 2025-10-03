from typing import TYPE_CHECKING

from fast_app import Notification

if TYPE_CHECKING:
    from fast_app import Model, NotificationChannel


class NewClass(Notification):
    def __init__(self, *args, **kwargs):
        pass

    def via(self, notifiable: 'Model') -> list['NotificationChannel']:
        return []
