from __future__ import annotations

from typing import Any, ClassVar, Optional

import pytest
from fast_validation import ValidationRuleException

from fast_app.contracts.model import Model
from fast_app.core.validation_rules.exists_validator_rule import ExistsValidatorRule


class EmailOTP(Model):
    email: Optional[str] = None


class AuditLog(Model):
    title: Optional[str] = None
    email_otp_id: Optional[str] = None

    search_fields = ["title"]
    search_relations = [
        {"field": "email_otp_id", "model": "EmailOTP", "search_fields": ["email"]}
    ]

    _last_pipeline: ClassVar[Optional[list[dict[str, Any]]]] = None
    _query_modifier_calls: ClassVar[list[tuple[Optional[str], Optional[str]]]] = []

    @classmethod
    async def query_modifier(
        cls,
        query: dict,
        function_name: str | None = None,
        model_name: str | None = None,
    ) -> dict:
        cls._query_modifier_calls.append((function_name, model_name))
        return query

    @classmethod
    async def aggregate(cls, pipeline: list[dict[str, Any]], **kwargs) -> list[dict[str, Any]]:
        cls._last_pipeline = pipeline
        return [{"data": [], "count": []}]


def test_collection_name_uses_pascal_case_to_snake_case():
    assert EmailOTP.collection_name() == "email_otp"


@pytest.mark.asyncio
async def test_search_relations_use_model_collection_name_logic():
    AuditLog._last_pipeline = None
    AuditLog._query_modifier_calls = []

    await AuditLog.search("alice")

    assert AuditLog._last_pipeline is not None
    union_stage = next(stage for stage in AuditLog._last_pipeline if "$unionWith" in stage)
    assert union_stage["$unionWith"]["coll"] == "email_otp"
    assert ("search", "email_otp") in AuditLog._query_modifier_calls


@pytest.mark.asyncio
async def test_exists_validator_rule_display_name_uses_snake_case():
    rule = ExistsValidatorRule(model=EmailOTP, is_object_id=True)

    with pytest.raises(ValidationRuleException) as exc:
        await rule.validate(value="bad_object_id", data={}, loc=())

    assert "email_otp_id" in str(exc.value)
