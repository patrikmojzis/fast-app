from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app.notification_base import Notification


class RoutesNotifications:
    """Use as parent class for models that are notifiable."""

    async def notify(self, notification: 'Notification'):
        await notification.send(self)
