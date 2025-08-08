import asyncio
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from quart import jsonify, Response

from fast_app.model_base import Model
from fast_app.utils.serialisation import serialise


class Resource(ABC):

    def __init__(self, data: Model | list[Model]):
        """
        Base class for all resources. Put Model or list[Model] in the constructor.
        """
        self._data = data

    async def dump(self) -> dict | list[dict]:
        """
        Dump the resource to a dictionary or list of dictionaries.
        """
        if isinstance(self._data, Model):
            data = await self.to_dict(self._data)
        else:
            data = await asyncio.gather(*(self.to_dict(res) for res in self._data)) 
        return serialise(data)

    async def to_response(self) -> Response:
        """
        Return the resource as a Quart response.
        """
        return jsonify(await self.dump())

    @abstractmethod
    async def to_dict(self, data: Model) -> dict:
        """
        Set up the resource to be dumped.
        """
        return data.dict()
