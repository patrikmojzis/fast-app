from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app.notification_base import Notification
    from fast_app.model_base import Model

class NotificationChannel(ABC):
    
    @abstractmethod
    async def send(self, notifiable: 'Model', notification: 'Notification'):
        pass