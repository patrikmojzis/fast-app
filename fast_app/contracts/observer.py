from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app import Model

class Observer(ABC):

    async def on_creating(self, model: 'Model'):
        """Before the model is created in the database."""
        pass

    async def on_created(self, model: 'Model'):
        """After the model is created in the database."""
        pass

    async def on_updating(self, model: 'Model'):
        """Before the model is updated in the database."""
        pass

    async def on_updated(self, model: 'Model'):
        """After the model is updated in the database."""
        pass

    async def on_deleting(self, model: 'Model'):
        """Before the model is deleted from the database."""
        pass

    async def on_deleted(self, model: 'Model'):
        """After the model is deleted from the database."""
        pass


