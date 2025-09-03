"""Migration contract for app-local database/file migrations."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from fast_app.app_provider import boot


class Migration(ABC):
    def boot(self) -> None:
        """Optional setup before running the migration."""
        boot()

    @abstractmethod
    def migrate(self) -> Any:
        """Run the migration asynchronously."""
        raise NotImplementedError


