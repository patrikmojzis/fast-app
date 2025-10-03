from datetime import datetime
from typing import Optional

from fast_app import Model, notifiable, authorizable


@notifiable
@authorizable
class User(Model):
    name: str = None
    email: str = None
    last_seen_at: Optional[datetime] = None

