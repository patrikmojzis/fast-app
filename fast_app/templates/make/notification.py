from fast_app import Notification
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app import Model, NotificationChannel


class Notification(Notification):
    
    def via(self, notifiable: 'Model') -> list['NotificationChannel']:
        return []
