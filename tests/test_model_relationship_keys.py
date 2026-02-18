from __future__ import annotations

from typing import Any, ClassVar, Optional

import pytest
from bson import ObjectId

from fast_app.contracts.model import Model


class ChatQuery(Model):
    _last_find_one_query: ClassVar[Optional[dict[str, Any]]] = None

    @classmethod
    async def find_one(cls, query: dict[str, Any], **kwargs):  # pragma: no cover - simple test stub
        cls._last_find_one_query = query
        return cls(_id=query.get("_id"))


class Usage(Model):
    chat_query_id: Optional[ObjectId] = None


class UsageEntry(Model):
    chat_query_id: Optional[ObjectId] = None
    _last_find_one_query: ClassVar[Optional[dict[str, Any]]] = None
    _last_find_query: ClassVar[Optional[dict[str, Any]]] = None
    _last_find_kwargs: ClassVar[Optional[dict[str, Any]]] = None

    @classmethod
    async def find_one(cls, query: dict[str, Any], **kwargs):
        cls._last_find_one_query = query
        return cls(chat_query_id=query.get("chat_query_id"))

    @classmethod
    async def find(cls, query: dict[str, Any], **kwargs):
        cls._last_find_query = query
        cls._last_find_kwargs = kwargs
        return [cls(chat_query_id=query.get("chat_query_id"))]


@pytest.mark.asyncio
async def test_belongs_to_uses_snake_case_default_child_key():
    ChatQuery._last_find_one_query = None
    chat_query_id = ObjectId()
    usage = Usage(chat_query_id=chat_query_id)

    related = await usage.belongs_to(ChatQuery)

    assert isinstance(related, ChatQuery)
    assert ChatQuery._last_find_one_query == {"_id": chat_query_id}


@pytest.mark.asyncio
async def test_belongs_to_returns_none_when_default_child_key_missing():
    ChatQuery._last_find_one_query = None
    usage = Usage()

    related = await usage.belongs_to(ChatQuery)

    assert related is None
    assert ChatQuery._last_find_one_query is None


@pytest.mark.asyncio
async def test_has_one_and_has_many_use_snake_case_default_child_key():
    UsageEntry._last_find_one_query = None
    UsageEntry._last_find_query = None
    UsageEntry._last_find_kwargs = None

    chat_query_id = ObjectId()
    chat_query = ChatQuery(_id=chat_query_id)

    one = await chat_query.has_one(UsageEntry)
    many = await chat_query.has_many(UsageEntry)

    assert isinstance(one, UsageEntry)
    assert isinstance(many, list)
    assert UsageEntry._last_find_one_query == {"chat_query_id": chat_query_id}
    assert UsageEntry._last_find_query == {"chat_query_id": chat_query_id}
    assert UsageEntry._last_find_kwargs == {"sort": [("_id", -1)]}
