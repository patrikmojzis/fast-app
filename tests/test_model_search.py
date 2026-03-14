from __future__ import annotations

from typing import Any, ClassVar, Optional

import pytest
from bson import ObjectId

from fast_app.contracts.model import Model
from fast_app.utils.model_utils import (
    MAX_SEARCH_TOKENS,
    MATCH_NOTHING_QUERY,
    build_search_query_from_string,
)


class SearchProbe(Model):
    title: Optional[str] = None
    description: Optional[str] = None
    is_active: Optional[bool] = None
    owner_id: Optional[ObjectId] = None

    _last_pipeline: ClassVar[Optional[list[dict[str, Any]]]] = None

    @classmethod
    async def query_modifier(
        cls,
        query: dict,
        function_name: str | None = None,
        model_name: str | None = None,
    ) -> dict:
        return query

    @classmethod
    async def aggregate(
        cls, pipeline: list[dict[str, Any]], **kwargs
    ) -> list[dict[str, Any]]:
        cls._last_pipeline = pipeline
        return [{"data": [], "count": []}]


class NonTextSearchProbe(Model):
    is_active: Optional[bool] = None
    owner_id: Optional[ObjectId] = None

    _last_pipeline: ClassVar[Optional[list[dict[str, Any]]]] = None

    @classmethod
    async def query_modifier(
        cls,
        query: dict,
        function_name: str | None = None,
        model_name: str | None = None,
    ) -> dict:
        return query

    @classmethod
    async def aggregate(
        cls, pipeline: list[dict[str, Any]], **kwargs
    ) -> list[dict[str, Any]]:
        cls._last_pipeline = pipeline
        return [{"data": [], "count": []}]


def test_build_search_query_from_string_removes_redundant_wildcards():
    query = build_search_query_from_string("alice", ["title"])

    regex = query["$and"][0]["$or"][0]["title"]["$regex"]
    assert regex.startswith("[")
    assert ".*" not in regex


def test_build_search_query_from_string_dedupes_and_limits_terms():
    query = build_search_query_from_string(
        "a alice Alice b 7 7 bob carl dave eve frank grace heidi ivan judy mallory",
        ["title"],
    )

    conditions = query["$and"]
    assert len(conditions) == MAX_SEARCH_TOKENS

    tokens = [condition["$or"][0]["title"]["$regex"] for condition in conditions]
    assert all(".*" not in token for token in tokens)
    assert (
        tokens[0]
        == build_search_query_from_string("alice", ["title"])["$and"][0]["$or"][0][
            "title"
        ]["$regex"]
    )
    assert build_search_query_from_string("a", ["title"]) == {}


def test_searchable_fields_defaults_to_text_mode():
    assert SearchProbe.searchable_fields() == ["title", "description"]
    assert SearchProbe.searchable_fields(mode="all") == [
        "_id",
        "created_at",
        "updated_at",
        "title",
        "description",
        "is_active",
        "owner_id",
    ]


@pytest.mark.asyncio
async def test_string_search_uses_only_text_fields_by_default():
    SearchProbe._last_pipeline = None

    await SearchProbe.search("alice")

    assert SearchProbe._last_pipeline is not None
    match_query = SearchProbe._last_pipeline[0]["$match"]
    field_names = {
        next(iter(condition.keys()))
        for word_condition in match_query["$and"]
        for condition in word_condition["$or"]
    }

    assert field_names == {"title", "description"}


@pytest.mark.asyncio
async def test_string_search_without_text_fields_matches_nothing():
    NonTextSearchProbe._last_pipeline = None

    await NonTextSearchProbe.search("alice")

    assert NonTextSearchProbe._last_pipeline is not None
    assert NonTextSearchProbe._last_pipeline[0]["$match"] == MATCH_NOTHING_QUERY


@pytest.mark.asyncio
async def test_object_id_search_keeps_non_text_default_fields():
    SearchProbe._last_pipeline = None
    query_id = ObjectId()

    await SearchProbe.search(query_id)

    assert SearchProbe._last_pipeline is not None
    clauses = SearchProbe._last_pipeline[0]["$match"]["$or"]
    assert any("owner_id" in clause for clause in clauses)
