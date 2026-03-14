from __future__ import annotations

from typing import Any, ClassVar, Optional

import pytest
from bson import ObjectId

from fast_app.contracts.model import Model
from fast_app.core.model_batch_cache import ModelBatchCache


class ChatQuery(Model):
    _last_find_query: ClassVar[Optional[dict[str, Any]]] = None

    @classmethod
    async def find(cls, query: dict[str, Any], **kwargs):
        cls._last_find_query = query
        in_keys = query.get("_id", {}).get("$in", [])
        return [cls(_id=k) for k in in_keys]

    @classmethod
    async def query_modifier(cls, query, function_name=None, model_name=None):
        return query


class Usage(Model):
    chat_query_id: Optional[ObjectId] = None


class UsageEntry(Model):
    chat_query_id: Optional[ObjectId] = None
    _last_find_query: ClassVar[Optional[dict[str, Any]]] = None
    _last_find_kwargs: ClassVar[Optional[dict[str, Any]]] = None

    @classmethod
    async def find(cls, query: dict[str, Any], **kwargs):
        cls._last_find_query = query
        cls._last_find_kwargs = kwargs
        fk = "chat_query_id"
        fk_val = query.get(fk)
        if isinstance(fk_val, dict) and "$in" in fk_val:
            return [cls(chat_query_id=k) for k in fk_val["$in"]]
        return [cls(**{fk: fk_val})]

    @classmethod
    async def query_modifier(cls, query, function_name=None, model_name=None):
        return query


@pytest.fixture(autouse=True)
def _reset_batch_cache():
    ModelBatchCache.reset()
    ModelBatchCache.ensure_active()
    yield
    ModelBatchCache.reset()


@pytest.mark.asyncio
async def test_belongs_to_uses_snake_case_default_child_key():
    ChatQuery._last_find_query = None
    chat_query_id = ObjectId()
    usage = Usage(chat_query_id=chat_query_id)

    related = await usage.belongs_to(ChatQuery)

    assert isinstance(related, ChatQuery)
    assert ChatQuery._last_find_query == {"_id": {"$in": [chat_query_id]}}


@pytest.mark.asyncio
async def test_belongs_to_returns_none_when_default_child_key_missing():
    ChatQuery._last_find_query = None
    usage = Usage()

    related = await usage.belongs_to(ChatQuery)

    assert related is None
    assert ChatQuery._last_find_query is None


@pytest.mark.asyncio
async def test_has_one_uses_snake_case_default_child_key():
    UsageEntry._last_find_query = None

    chat_query_id = ObjectId()
    chat_query = ChatQuery(_id=chat_query_id)

    one = await chat_query.has_one(UsageEntry)

    assert isinstance(one, UsageEntry)
    assert UsageEntry._last_find_query == {"chat_query_id": {"$in": [chat_query_id]}}


@pytest.mark.asyncio
async def test_has_many_uses_snake_case_default_child_key():
    UsageEntry._last_find_query = None
    UsageEntry._last_find_kwargs = None

    chat_query_id = ObjectId()
    chat_query = ChatQuery(_id=chat_query_id)

    many = await chat_query.has_many(UsageEntry)

    assert isinstance(many, list)
    assert UsageEntry._last_find_query == {"chat_query_id": chat_query_id}
    assert UsageEntry._last_find_kwargs == {"sort": [("_id", -1)]}
