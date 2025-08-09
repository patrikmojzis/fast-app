import pytest
from quart import Quart

from fast_app.core.simple_controller import simple_index
from fast_app.utils.model_utils import build_search_query_from_string


class DummyResource:
    def __init__(self, data):
        self.data = data

    async def dump(self):
        return self.data


class DummyModel:
    search_called_with = None
    count_called_with = None
    find_called_with = None

    @classmethod
    def all_fields(cls):
        return ["name"]

    @classmethod
    async def search(cls, query, limit, skip, sort=None):
        cls.search_called_with = query
        return {"meta": {}, "data": [{"name": "a"}]}

    @classmethod
    async def count(cls, query):
        cls.count_called_with = query
        return 1

    @classmethod
    async def find(cls, query, limit, skip, sort=None):
        cls.find_called_with = query
        return [{"name": "a"}]


@pytest.mark.asyncio
async def test_simple_index_pagination_and_search():
    app = Quart(__name__)

    # Pagination without search
    async with app.test_request_context("/?page=1&per_page=1"):
        DummyModel.search_called_with = None
        DummyModel.count_called_with = None
        DummyModel.find_called_with = None
        response = await simple_index(DummyModel, DummyResource, extended_query={"active": True})
        await response.get_json()
        assert DummyModel.count_called_with == {"active": True}
        assert DummyModel.find_called_with == {"active": True}
        assert DummyModel.search_called_with is None

    # Search with query
    async with app.test_request_context("/?search=foo"):
        DummyModel.search_called_with = None
        response = await simple_index(DummyModel, DummyResource, extended_query={"active": True})
        await response.get_json()
        expected = {
            "$and": [
                {"active": True},
                build_search_query_from_string("foo", ["name"]),
            ]
        }
        assert DummyModel.search_called_with == expected
