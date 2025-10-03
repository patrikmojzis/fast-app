import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Union, Any

from quart import jsonify, Response

from fast_app.utils.serialisation import serialise

if TYPE_CHECKING:
    from fast_app.contracts.model import Model

class Resource(ABC):

    def __init__(self, data: Union['Model', list['Model'], None]):
        """
        Base class for all resources. Put Model or list[Model] in the constructor.
        """
        self._data = data

    async def dump(self) -> dict | list[dict] | None:
        """
        Dump the resource to a dictionary or list of dictionaries.
        """
        if self._data is None:
            return None

        if isinstance(self._data, list):
            data = await asyncio.gather(*(self.to_dict(res) for res in self._data))
        else:
            data = await self.to_dict(self._data)

        # Resolve any nested Resource instances concurrently
        resolved = await self._resolve_resources(data)
        return serialise(resolved)

    async def _resolve_resources(self, value: Any) -> Any:
        """
        Recursively resolve nested Resource instances within dicts/lists in parallel.
        """
        # Direct Resource instance
        if isinstance(value, Resource):
            return await value.dump()

        # Lists: resolve all items concurrently
        if isinstance(value, list):
            return await asyncio.gather(*(self._resolve_resources(item) for item in value))

        # Dicts: resolve all values concurrently (preserve keys/order)
        if isinstance(value, dict):
            keys = list(value.keys())
            resolved_vals = await asyncio.gather(*(self._resolve_resources(value[k]) for k in keys))
            return {k: v for k, v in zip(keys, resolved_vals)}

        # Primitives and everything else pass through
        return value

    async def to_response(self) -> Response:
        """
        Return the resource as a Quart response.
        """
        return jsonify(await self.dump())

    @abstractmethod
    async def to_dict(self, data: 'Model') -> dict:
        """
        Set up the resource to be dumped.
        """
        return data.dict()

