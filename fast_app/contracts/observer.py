from abc import ABC
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from fast_app.model_base import Model

class Observer(ABC):

    async def on_updating(self, model: 'Model'):
        pass

    async def on_creating(self, model: 'Model'):
        pass

    async def on_deleting(self, model: 'Model'):
        pass

    async def on_updated(self, model: 'Model'):
        pass

    async def on_created(self, model: 'Model'):
        pass

    async def on_deleted(self, model: 'Model'):
        pass
