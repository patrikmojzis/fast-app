from __future__ import annotations

import copy
from dataclasses import dataclass
from typing import Any, Callable, Dict, Generic, Optional, TypeVar, TYPE_CHECKING

from bson import ObjectId

try:  # pragma: no cover - import guard for optional faker dependency
    from faker import Faker as _Faker  # type: ignore
except ModuleNotFoundError:  # pragma: no cover
    _Faker = None  # type: ignore

from fast_app.utils.datetime_utils import now
from fast_app.utils.model_resolver import resolve_model_from_name

if TYPE_CHECKING:  # pragma: no cover
    from fast_app.contracts.model import Model


TModel = TypeVar("TModel", bound="Model")


class FactoryAttribute:
    """Base descriptor used by factories to produce field values."""

    name: Optional[str] = None
    requires_faker: bool = True

    def clone(self) -> FactoryAttribute:
        return copy.deepcopy(self)

    def bind(self, factory_cls: type[Factory[Any]], name: str) -> FactoryAttribute:
        self.name = name
        return self

    def generate(self, faker: Optional[_Faker]) -> Any:
        raise NotImplementedError


class FakerAttribute(FactoryAttribute):
    """Factory attribute that pulls data from the Faker provider."""

    def __init__(self, provider: str, *args: Any, **kwargs: Any) -> None:
        self.provider = provider
        self.args = args
        self.kwargs = kwargs

    def generate(self, faker: Optional[_Faker]) -> Any:
        if faker is None:  # pragma: no cover - safeguard
            raise RuntimeError("Faker provider requested without Faker installed.")
        provider = getattr(faker, self.provider)
        return provider(*self.args, **self.kwargs)


class ValueAttribute(FactoryAttribute):
    """Factory attribute that always returns the provided value."""

    def __init__(self, value: Any) -> None:
        self.value = value
        self.requires_faker = False

    def generate(self, faker: Optional[_Faker]) -> Any:  # pragma: no cover - faker unused
        return self.value


class CallableAttribute(FactoryAttribute):
    """Factory attribute backed by a callable receiving the faker instance."""

    def __init__(
        self,
        generator: Callable[[Optional[_Faker]], Any],
        *,
        requires_faker: bool = True,
    ) -> None:
        self.generator = generator
        self.requires_faker = requires_faker

    def generate(self, faker: Optional[_Faker]) -> Any:
        return self.generator(faker)


class FunctionAttribute(FactoryAttribute):
    """Factory attribute that calls a given function without providing faker."""

    def __init__(self, func: Callable[..., Any], *args: Any, **kwargs: Any) -> None:
        self.func = func
        self.args = args
        self.kwargs = kwargs
        self.requires_faker = False

    def generate(self, faker: Optional[_Faker]) -> Any:  # pragma: no cover - faker unused
        return self.func(*self.args, **self.kwargs)


@dataclass(frozen=True)
class RelationSpec:
    """Configuration describing a related model to create alongside the parent."""

    model: type["Model"]
    factory_cls: type["Factory[Any]"]
    overrides: dict[str, Any]
    foreign_key: str


class FactoryMeta(type):
    """Metaclass collecting declared factory attributes on subclasses."""

    def __new__(mcls, name: str, bases: tuple[type, ...], attrs: dict[str, Any]):
        declared: dict[str, FactoryAttribute] = {}
        for base in bases:
            base_fields = getattr(base, "_declared_fields", None)
            if base_fields:
                declared.update({k: v.clone() for k, v in base_fields.items()})

        for attr_name, value in list(attrs.items()):
            if isinstance(value, FactoryAttribute):
                declared[attr_name] = value.clone()

        cls = super().__new__(mcls, name, bases, attrs)
        bound_fields = {}
        for field_name, field in declared.items():
            bound = field.bind(cls, field_name)
            setattr(cls, field_name, bound)
            bound_fields[field_name] = bound

        cls._declared_fields = bound_fields
        cls._faker = _Faker() if _Faker is not None else None
        return cls


class Factory(Generic[TModel], metaclass=FactoryMeta):
    """Base class for model factories."""

    def __init__(self, model_cls: type[TModel]) -> None:
        self._model = model_cls
        self._fillable = model_cls.fillable_fields()
        self._declared_fields = type(self)._declared_fields
        self._relations: list[RelationSpec] = []

    @property
    def faker(self) -> _Faker:
        faker = type(self)._faker
        if faker is None:
            raise RuntimeError(
                "Optional dependency 'Faker' is not installed. Install fast-app[dev] "
                "or add Faker to your project to use Faker-backed factory fields."
            )
        return faker

    def with_related(
        self,
        related: str | type["Model"],
        overrides: Optional[dict[str, Any]] = None,
        *,
        factory: Optional[type["Factory[Any]"] | "Factory[Any]"] = None,
        foreign_key: Optional[str] = None,
    ) -> Factory[TModel]:
        """Return a cloned factory that will create the related model."""
        spec = self._build_relation_spec(
            related,
            overrides or {},
            factory=factory,
            foreign_key=foreign_key,
        )
        clone = self._clone()
        clone._relations = [*self._relations, spec]
        return clone

    def _clone(self) -> Factory[TModel]:
        clone = type(self)(self._model)
        clone._relations = list(self._relations)
        return clone

    def _build_relation_spec(
        self,
        related: str | type["Model"],
        overrides: dict[str, Any],
        *,
        factory: Optional[type["Factory[Any]"] | "Factory[Any]"],
        foreign_key: Optional[str],
    ) -> RelationSpec:
        related_model = self._resolve_related_model(related)
        factory_cls = self._resolve_factory_cls(related_model, factory)
        fk_field = foreign_key or f"{related_model.collection_name()}_id"
        return RelationSpec(
            model=related_model,
            factory_cls=factory_cls,
            overrides=dict(overrides),
            foreign_key=fk_field,
        )

    def _resolve_related_model(self, related: str | type["Model"]) -> type["Model"]:
        ModelBase = self._get_model_base()
        if isinstance(related, type) and issubclass(related, ModelBase):
            return related
        if isinstance(related, str):
            return self._resolve_model_from_name(related, ModelBase)
        raise TypeError("related must be a Model subclass or string reference")

    @staticmethod
    def _get_model_base() -> type:
        from fast_app.contracts.model import Model  # local import to avoid cycles
        return Model

    def _resolve_model_from_name(self, name: str, base: type) -> type["Model"]:
        return resolve_model_from_name(name, base=base, module_hint=self._model.__module__)

    def _resolve_factory_cls(
        self,
        model: type["Model"],
        factory: Optional[type["Factory[Any]"] | "Factory[Any]"],
    ) -> type["Factory[Any]"]:
        if factory is not None:
            if isinstance(factory, type) and issubclass(factory, Factory):
                return factory
            if isinstance(factory, Factory):
                return type(factory)
            raise TypeError("factory must be a Factory subclass or instance")

        existing = getattr(model, "factory", None)
        if existing is None:
            raise ValueError(
                f"No factory registered for related model '{model.__name__}'. "
                "Pass a factory explicitly with the factory= argument."
            )
        return type(existing)

    def _instantiate_relation_factory(self, spec: RelationSpec) -> Factory[Any]:
        return spec.factory_cls(spec.model)

    def build_dict(self, **overrides: Any) -> Dict[str, Any]:
        values: Dict[str, Any] = {}
        remaining = dict(overrides)
        for name, attribute in self._declared_fields.items():
            if name in remaining:
                values[name] = remaining.pop(name)
            else:
                faker = self._get_faker_for(attribute)
                values[name] = attribute.generate(faker)
        if remaining:
            values.update(remaining)
        return values

    def _get_faker_for(self, attribute: FactoryAttribute) -> Optional[_Faker]:
        faker = type(self)._faker
        if faker is None:
            if attribute.requires_faker:
                raise RuntimeError(
                    "Optional dependency 'Faker' is not installed. Install fast-app[dev] "
                    "or add Faker to your project to use Faker-backed factory fields."
                )
            return None
        return faker

    def build(self, **overrides: Any) -> TModel:
        data = self.build_dict(**overrides)
        self._apply_relations_sync(data)
        return self._model(**data)

    async def create(self, **overrides: Any) -> TModel:
        data = self.build_dict(**overrides)
        await self._apply_relations_async(data, mode="create")
        return await self._model.create(data)

    async def seed(self, count: int, **overrides: Any) -> list[TModel]:
        if count <= 0:
            return []

        documents: list[dict[str, Any]] = []
        for _ in range(count):
            payload = self.build_dict(**overrides)
            await self._apply_relations_async(payload, mode="seed")
            allowed = {"_id", "created_at", "updated_at"}
            doc = {k: v for k, v in payload.items() if k in self._fillable or k in allowed}
            doc.setdefault("_id", ObjectId())
            doc.setdefault("created_at", now())
            doc.setdefault("updated_at", now())
            documents.append(doc)

        await self._model.insert_many(documents)
        return [self._model(**doc) for doc in documents]

    def _apply_relations_sync(self, payload: dict[str, Any]) -> None:
        for spec in self._relations:
            factory = self._instantiate_relation_factory(spec)
            related = factory.build(**spec.overrides)
            if getattr(related, "_id", None) is None:
                related._id = ObjectId()
            payload[spec.foreign_key] = related._id

    async def _apply_relations_async(self, payload: dict[str, Any], *, mode: str) -> None:
        for spec in self._relations:
            factory = self._instantiate_relation_factory(spec)
            if mode == "create":
                related = await factory.create(**spec.overrides)
            elif mode == "seed":
                created = await factory.seed(1, **spec.overrides)
                related = created[0]
            else:  # pragma: no cover - defensive
                raise ValueError(f"Unsupported relation mode '{mode}'")
            payload[spec.foreign_key] = related._id

    def count(self, amount: int) -> FactoryBatchBuilder[TModel]:
        if amount <= 0:
            raise ValueError("count must be positive")
        return FactoryBatchBuilder(self, amount)


class FactoryBatchBuilder(Generic[TModel]):
    """Chainable helper for batch operations (e.g., `.count(5).create()`)."""

    def __init__(self, factory: Factory[TModel], amount: int) -> None:
        self._factory = factory
        self._amount = amount

    def build(self, **overrides: Any) -> list[TModel]:
        return [self._factory.build(**overrides) for _ in range(self._amount)]

    async def create(self, **overrides: Any) -> list[TModel]:
        results: list[TModel] = []
        for _ in range(self._amount):
            results.append(await self._factory.create(**overrides))
        return results

    async def seed(self, **overrides: Any) -> list[TModel]:
        return await self._factory.seed(self._amount, **overrides)


Faker = FakerAttribute
Value = ValueAttribute
Function = FunctionAttribute
FactoryField = FactoryAttribute

__all__ = [
    "Factory",
    "FactoryBatchBuilder",
    "FactoryAttribute",
    "FactoryField",
    "FakerAttribute",
    "Faker",
    "ValueAttribute",
    "FunctionAttribute",
    "Function",
    "Value",
    "CallableAttribute",
]
