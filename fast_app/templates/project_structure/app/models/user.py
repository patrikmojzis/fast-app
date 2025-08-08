from datetime import datetime
from typing import Optional

from fast_app.model_base import Model
from fast_app.authorizable import Authorizable


class User(Model, Authorizable):
    name: str = None
    email: str = None
    last_seen_at: Optional[datetime] = None
