"""Seeder contract for app-local database seeders."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any
from fast_app.app_provider import boot


class Seeder(ABC):
    def boot(self) -> None:
        """Optional setup before running the seeder."""
        boot()

    @abstractmethod
    async def seed(self) -> Any:
        """Run the seeder asynchronously."""
        raise NotImplementedError


