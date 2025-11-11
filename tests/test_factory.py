from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, ClassVar, Optional

import pytest
from bson import ObjectId

from fast_app.contracts.factory import (
    CallableAttribute,
    Factory,
    Faker,
    Value,
    Function,
)
from fast_app.contracts.model import Model
from fast_app.utils.datetime_utils import now


class InMemoryModel(Model):
    """Model stub that stores created documents in memory for testing."""

    _storage: ClassVar[list[dict[str, Any]]] = []

    @classmethod
    def reset_storage(cls) -> None:
        cls._storage = []

    @classmethod
    async def create(cls, data: dict[str, Any]) -> "Model":
        document = dict(data)
        document.setdefault("_id", ObjectId())
        document.setdefault("created_at", now())
        document.setdefault("updated_at", now())
        cls._storage.append(document)
        return cls(**document)

    @classmethod
    async def insert_many(cls, data: list[dict[str, Any]]) -> None:  # pragma: no cover - simple stub
        cls._storage.extend(data)


class Business(InMemoryModel):
    name: str

    _storage: ClassVar[list[dict[str, Any]]] = []


class User(InMemoryModel):
    name: str
    email: str
    nickname: str
    business_id: Optional[ObjectId] = None
    expires_at: Optional[datetime] = None

    _storage: ClassVar[list[dict[str, Any]]] = []


class BusinessFactory(Factory[Business]):
    name = Value("Default Business")


class UserFactory(Factory[User]):
    name = CallableAttribute(lambda _: "callable-name", requires_faker=False)
    email = Value("const@example.com")
    nickname = Faker("user_name")
    expires_at = Function(lambda: datetime.now(timezone.utc))


@pytest.fixture(autouse=True)
def reset_in_memory_models():
    Business.reset_storage()
    User.reset_storage()
    Business.factory = BusinessFactory(Business)
    User.factory = UserFactory(User)
    yield
    Business.reset_storage()
    User.reset_storage()


def test_factory_build_produces_model_instance():
    factory = UserFactory(User)

    user = factory.build()

    assert isinstance(user, User)
    assert user.name == "callable-name"
    assert user.email == "const@example.com"
    assert isinstance(user.nickname, str) and user.nickname
    assert isinstance(user.expires_at, datetime)


def test_factory_build_allows_overrides():
    factory = UserFactory(User)

    custom_expiry = datetime(2030, 1, 1, tzinfo=timezone.utc)
    user = factory.build(name="override-name", expires_at=custom_expiry)

    assert user.name == "override-name"
    assert user.email == "const@example.com"
    assert user.expires_at == custom_expiry


def test_factory_batch_builder_respects_amount():
    factory = UserFactory(User)

    users = factory.count(3).build()

    assert len(users) == 3
    assert all(isinstance(user, User) for user in users)


@pytest.mark.asyncio
async def test_factory_seed_generates_documents_with_fillable_fields():
    factory = UserFactory(User)

    results = await factory.seed(2, email="override@example.com")

    assert len(results) == 2
    assert all(isinstance(instance, User) for instance in results)
    assert len(User._storage) == 2

    for document in User._storage:
        assert set(document.keys()) == {"_id", "created_at", "updated_at", "name", "email", "nickname", "expires_at"}
        assert document["email"] == "override@example.com"
        assert isinstance(document["name"], str)
        assert isinstance(document["nickname"], str)
        assert isinstance(document["expires_at"], datetime)


def test_factory_with_build_assigns_foreign_key():
    factory = UserFactory(User).with_related(Business, {"name": "Acme Corp"})

    user = factory.build()

    assert isinstance(user.business_id, ObjectId)


@pytest.mark.asyncio
async def test_factory_with_create_persists_related_and_sets_foreign_key():
    factory = UserFactory(User).with_related(Business, {"name": "Acme Corp"})

    user = await factory.create()

    assert isinstance(user.business_id, ObjectId)
    assert Business._storage[-1]["name"] == "Acme Corp"
    assert User._storage[-1]["business_id"] == user.business_id


@pytest.mark.asyncio
async def test_factory_with_seed_persists_related_models():
    users = await UserFactory(User).with_related("business", {"name": "Seed Corp"}).seed(1)

    assert len(users) == 1
    assert Business._storage[-1]["name"] == "Seed Corp"
    assert User._storage[-1]["business_id"] == Business._storage[-1]["_id"]
