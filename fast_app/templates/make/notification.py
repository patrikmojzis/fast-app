from fast_app.notification_base import Notification
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app.model_base import Model
    from fast_app.notification_channel_base import NotificationChannel


class Notification(Notification):
    
    def via(self, notifiable: 'Model') -> list['NotificationChannel']:
        return []