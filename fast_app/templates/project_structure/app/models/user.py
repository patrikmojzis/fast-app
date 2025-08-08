from datetime import datetime
from typing import Optional

from fast_app import Model, Authorizable


class User(Model, Authorizable):
    name: str = None
    email: str = None
    last_seen_at: Optional[datetime] = None

