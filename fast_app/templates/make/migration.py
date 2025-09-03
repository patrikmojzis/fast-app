from __future__ import annotations

from fast_app.contracts.migration import Migration
from fast_app.app_provider import boot


class NewClass(Migration):
    async def migrate(self) -> None:
        # Implement your async migration logic here
        pass


