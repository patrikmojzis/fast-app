import asyncio
import time
import pytest

from fast_app.contracts.resource import Resource


class DummyModel:
    def __init__(self, _id: int, name: str):
        self._id = _id
        self.name = name

    @property
    def id(self):
        return self._id

    def dict(self):
        return {"_id": self._id, "name": self.name}


class Rep(DummyModel):
    pass


class County(DummyModel):
    def __init__(self, _id: int, name: str, rep: Rep | None, delay: float = 0.0):
        super().__init__(_id, name)
        self._rep = rep
        self._delay = delay

    async def rep(self):
        # Simulate IO
        if self._delay:
            await asyncio.sleep(self._delay)
        return self._rep


class RepResource(Resource):
    async def to_dict(self, rep: Rep):
        return {"_id": rep.id, "name": rep.name}


class CountyResource(Resource):
    async def to_dict(self, county: County):
        return {
            "_id": county.id,
            "name": county.name,
            # Nested resource created directly. If county.rep() returns None, Resource handles it.
            "rep": RepResource(await county.rep()),
        }


@pytest.mark.asyncio
async def test_nested_resource_resolves_and_serialises():
    rep = Rep(10, "Alice")
    county = County(1, "Kings", rep)
    res = CountyResource(county)
    dumped = await res.dump()
    assert dumped == {"_id": 1, "name": "Kings", "rep": {"_id": 10, "name": "Alice"}}


@pytest.mark.asyncio
async def test_none_propagates_to_nested_resource():
    county = County(2, "Queens", None)
    res = CountyResource(county)
    dumped = await res.dump()
    assert dumped == {"_id": 2, "name": "Queens", "rep": None}


@pytest.mark.asyncio
async def test_list_concurrent_resolution():
    # Two counties with slow rep() to verify concurrent awaiting inside list handling
    rep1 = Rep(21, "Bob")
    rep2 = Rep(22, "Carol")
    counties = [County(3, "Bronx", rep1, delay=0.2), County(4, "Nassau", rep2, delay=0.2)]

    start = time.perf_counter()
    res = CountyResource(counties)
    dumped = await res.dump()
    elapsed = time.perf_counter() - start

    # Should complete around ~0.2s (plus small overhead), not ~0.4s, indicating concurrency.
    assert elapsed < 0.35, f"Expected concurrent resolution, took {elapsed:.3f}s"
    assert dumped == [
        {"_id": 3, "name": "Bronx", "rep": {"_id": 21, "name": "Bob"}},
        {"_id": 4, "name": "Nassau", "rep": {"_id": 22, "name": "Carol"}},
    ]


