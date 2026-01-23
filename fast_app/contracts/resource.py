import asyncio
import inspect
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Union, Any, Awaitable, Optional

from quart import jsonify, Response

from fast_app.utils.serialisation import serialise

if TYPE_CHECKING:
    from fast_app.contracts.model import Model

ModelT = "Model"
DataT = Union[
    "Model",
    list["Model"],
    None,
    Awaitable[Optional["Model"]],
    Awaitable[Optional[list["Model"]]],
]

class Resource(ABC):
    def __init__(self, data: DataT):
        """
        Base class for all resources.
        Supports:
          - Model | list[Model] | None
          - Awaitable[Model | list[Model] | None]
        """
        self._data = data

    async def dump(self) -> dict | list[dict] | None:
        data = await self._maybe_await(self._data)

        if data is None:
            return None

        if isinstance(data, list):
            # Build per-item dicts concurrently (if to_dict does I/O)
            raw_items = await asyncio.gather(
                *(self._maybe_await(self.to_dict(item)) for item in data)
            )
            resolved = await self._resolve(raw_items)
            return serialise(resolved)

        raw = await self._maybe_await(self.to_dict(data))
        resolved = await self._resolve(raw)
        return serialise(resolved)

    async def to_response(self) -> Response:
        return jsonify(await self.dump())

    async def _maybe_await(self, value: Any) -> Any:
        """Helper to await a value if it's awaitable, otherwise return as-is."""
        return await value if inspect.isawaitable(value) else value

    async def _resolve(self, value: Any) -> Any:
        """
        Recursively resolve:
          - awaitables (coroutines/futures/tasks)
          - nested Resource instances
          - dicts/lists containing either of the above
        All collections resolve in parallel via asyncio.gather().
        """
        # 1) awaitables first
        if inspect.isawaitable(value):
            return await self._resolve(await value)

        # 2) Resource instances (which themselves may wrap awaitables)
        if isinstance(value, Resource):
            return await value.dump()

        # 3) lists
        if isinstance(value, list):
            return await asyncio.gather(*(self._resolve(v) for v in value))

        # 4) dicts (preserve key order)
        if isinstance(value, dict):
            items = list(value.items())
            resolved_vals = await asyncio.gather(*(self._resolve(v) for _, v in items))
            return {k: rv for (k, _), rv in zip(items, resolved_vals)}

        # 5) primitives/objects pass through
        return value

    @abstractmethod
    async def to_dict(self, data: "Model") -> dict:
        ...