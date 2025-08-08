from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app import Model, Notification

class NotificationChannel(ABC):
    
    @abstractmethod
    async def send(self, notifiable: 'Model', notification: 'Notification'):
        pass
