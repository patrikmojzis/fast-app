from typing import TYPE_CHECKING

from fast_app import Observer

if TYPE_CHECKING:
    from fast_app import Model


class NewClass(Observer):
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
