# app/models/model.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TypeVar, ClassVar, Any, get_type_hints, get_origin, Self, Union
from typing import TYPE_CHECKING

from bson import ObjectId

from fast_app.contracts.policy import Policy
from fast_app.database.mongo import get_db
from fast_app.decorators.db_cache_decorator import cached_db_retrieval
from fast_app.exceptions.common_exceptions import DatabaseNotInitializedException
from fast_app.exceptions.model_exceptions import ModelNotFoundException
from fast_app.utils.model_utils import build_search_query_from_string
from fast_app.utils.query_builder import QueryBuilder
from fast_app.utils.serialisation import serialise
from fast_app.utils.versioned_cache import bump_collection_version
from fast_app.utils.datetime_utils import now

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorCommandCursor, AsyncIOMotorCursor
    from fast_app import Observer
    from fast_app.contracts.policy import Policy


T = TypeVar('T', bound='Model')


@dataclass
class Model:
    protected: ClassVar[list[str]] = ["_id", "created_at", "updated_at"]

    policy: ClassVar[Optional['Policy']] = None
    _cached_model_fields: ClassVar[Optional[dict[str, Any]]] = None
    _cached_fillable_fields: ClassVar[Optional[list[str]]] = None
    _cached_all_fields: ClassVar[Optional[list[str]]] = None

    search_relations: ClassVar[list[dict[str, str]]] = []  # Example: [{"field": "user_id", "model": "User", "search_fields": ["name"]}]
    search_fields: ClassVar[Optional[list[str]]] = None

    _id: Optional[ObjectId] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __init__(self, *args, **kwargs):
        self.observers: list['Observer'] = [] 
        self.clean: dict[str, Any] = {}

        is_from_db = '_id' in kwargs and kwargs['_id'] is not None

        for key, value in kwargs.items():
            if key in self.model_fields().keys():
                if is_from_db:
                    super().__setattr__(key, value)
                else:
                    setattr(self, key, value)

    def __str__(self):
        return str(self.dict())

    @classmethod
    def collection_name(cls) -> str:
        return cls.__name__.lower()

    @classmethod
    async def collection_cls(cls) -> 'AsyncIOMotorCollection':
        db = await get_db()
        if db is None:
            raise DatabaseNotInitializedException()
        return db[cls.collection_name()]

    async def collection(self) -> 'AsyncIOMotorCollection':
        db = await get_db()
        if db is None:
            raise DatabaseNotInitializedException()
        return db[self.collection_name()]

    @classmethod
    @cached_db_retrieval()
    async def exec_find(cls, *args, **kwargs) -> 'AsyncIOMotorCursor':
        cursor = (await cls.collection_cls()).find(*args, **kwargs)
        return [d async for d in cursor]

    @classmethod
    @cached_db_retrieval()
    async def exec_find_one(cls, *args, **kwargs) -> Optional[dict[str, Any]]:
        return await (await cls.collection_cls()).find_one(*args, **kwargs)

    @classmethod
    @cached_db_retrieval()
    async def exec_count(cls, *args, **kwargs) -> int:
        return await (await cls.collection_cls()).count_documents(*args, **kwargs)

    async def save(self) -> Self:
        if self._id:
            await self._update()
        else:
            await self._create()
        return self

    @classmethod
    def model_fields(cls) -> dict[str, Any]:
        if cls._cached_model_fields is not None:
            return cls._cached_model_fields

        annotations: dict[str, Any] = {}
        for base in cls.__mro__:
            if hasattr(base, '__annotations__'):
                base_hints = get_type_hints(base)
                for name, hint in base_hints.items():
                    # Skip ClassVar annotations and internal control fields
                    if get_origin(hint) is ClassVar:
                        continue

                    if name in ("protected", "policy", "search_relations", "search_fields"):  # May be redundant
                        continue
                    annotations[name] = hint

        cls._cached_model_fields = annotations
        return annotations

    @classmethod
    def fillable_fields(cls) -> list[str]:
        if cls._cached_fillable_fields is not None:
            return cls._cached_fillable_fields
        cls._cached_fillable_fields = [f for f in cls.model_fields().keys() if f not in cls.protected]
        return cls._cached_fillable_fields

    @classmethod
    def all_fields(cls) -> list[str]:
        if cls._cached_all_fields is not None:
            return cls._cached_all_fields
        cls._cached_all_fields = [key for key in cls.model_fields().keys()]
        return cls._cached_all_fields

    @classmethod
    def searchable_fields(cls) -> list[str]:
        if cls.search_fields:
            return cls.search_fields
        return cls.all_fields()

    async def _notify_observer(self, hook: str) -> None:
        for observer in self.observers:
            await getattr(observer, hook)(self)

    @staticmethod
    def _build_update_payload(
        set_values: Optional[dict[str, Any]] = None,
        extra_ops: Optional[dict[str, Any]] = None,
        touch_timestamp: bool = True,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {}
        if extra_ops:
            payload.update({k: v for k, v in extra_ops.items() if k != "$set"})
        if set_values:
            if "$set" in payload and isinstance(payload["$set"], dict):
                payload["$set"].update(set_values)
            else:
                payload["$set"] = dict(set_values)
        if touch_timestamp:
            payload.setdefault("$currentDate", {})
            if isinstance(payload["$currentDate"], dict):
                payload["$currentDate"]["updated_at"] = True
            else:
                payload["$currentDate"] = {"updated_at": True}
        return payload

    async def _update(self) -> None:
        await self._notify_observer('on_updating')
        coll = await self.collection()
        query = await self.query_modifier({'_id': self._id}, "update", self.collection_name())
        update_payload = self._build_update_payload(
            set_values={key: self.get(key) for key in self.clean.keys()},
            extra_ops=None,
            touch_timestamp=True,
        )
        await coll.update_one(query, update_payload)
        await self.refresh()
        bump_collection_version(self.collection_name())
        await self._notify_observer('on_updated')

    async def _create(self) -> None:
        await self._notify_observer('on_creating')
        to_insert = {
            **{key: self.get(key) for key in self.fillable_fields()},
            'created_at': self.get('created_at') or now(),
            'updated_at': self.get('updated_at') or now(),
        }
        data = await self.query_modifier(to_insert, "create", self.collection_name())
        coll = await self.collection()
        result = await coll.insert_one(data)
        self._id = result.inserted_id
        await self.refresh()
        bump_collection_version(self.collection_name())
        await self._notify_observer('on_created')

    @classmethod
    async def create(cls: type[T], data: dict[str, Any]) -> T:
        instance = cls(**data)
        await instance.save()
        return instance

    @classmethod
    async def all(cls: type[T]) -> list[T]:
        return await cls.find({})

    async def refresh(self) -> Self:
        coll = await self.collection()
        data = await coll.find_one({'_id': self._id})
        if data:
            for key, value in data.items():
                setattr(self, key, value)
            self.clean = {}
        return self

    @classmethod
    async def search(cls: type[T], query: str | dict[str, Any] | ObjectId | int, limit: int = 10, skip: int = 0, 
                                   sort: Optional[list[tuple[str, int]]] = None) -> dict[str, Any]:
        """
        Search for records in the current collection and related collections.
        """
        # Convert query to string if it's an int or ObjectId
        search_fields = cls.searchable_fields()

        if isinstance(query, int):
            query = str(query)
        elif isinstance(query, ObjectId):
            query = {"$or": [{key: query} for key in search_fields]}
            
        current_collection = cls.collection_name()
        
        # Start with direct matches in the current collection
        pipeline = []
        
        # Query for current collection
        base_query = await cls.query_modifier({}, "search", current_collection) 
        
        # Find direct matches first
        direct_match = {
            "$match": {
                "$and": [
                    base_query,
                    build_search_query_from_string(query, search_fields) if isinstance(query, str) else query # Build query from string or use custom
                ]
            }
        }
        pipeline.append(direct_match)
        
        # Use relations search only if searching text
        if isinstance(query, str):
            # Add unionWith for each relation to combine results with related lookups
            for relation in cls.search_relations:
                related_model_name = relation["model"].lower()
                foreign_key = relation["field"]
                relation_fields = [field for field in relation.get("search_fields", []) if field]
                if not relation_fields:
                    continue
                                
                # Add unionWith to include related matches
                pipeline.append({
                    "$unionWith": {
                        "coll": related_model_name,
                        "pipeline": [
                            # Find documents in the related collection matching the search query
                            {"$match": {
                                "$and": [
                                    await cls.query_modifier({}, "search", related_model_name),
                                    build_search_query_from_string(query, relation_fields)
                                ]
                            }},
                            # Look up records in the current collection that reference these matches
                            {"$lookup": {
                                "from": current_collection,
                                "localField": "_id",
                                "foreignField": foreign_key,
                                "as": "matches"
                            }},
                            # Unwind to get individual records
                            {"$unwind": {"path": "$matches"}},
                            # Keep only the matching records from the current collection
                            {"$replaceRoot": {"newRoot": "$matches"}},
                            # Apply query context
                            {"$match": base_query}
                        ]
                    }
                })
        
        # After collecting all matches, remove duplicates before pagination
        # Use $group with _id to keep only unique documents
        pipeline.append({
            "$group": {
                "_id": "$_id",
                "doc": {"$first": "$$ROOT"}
            }
        })
        
        # Replace root with the deduplicated document
        pipeline.append({
            "$replaceRoot": {"newRoot": "$doc"}
        })
        
        # Apply sort if provided, or default to _id for deterministic ordering
        user_sort = None
        if sort:
            user_sort = {"$sort": {field: direction for field, direction in sort}}
            pipeline.append(user_sort)
        else:
            # Sort by _id for deterministic paging
            pipeline.append({"$sort": {"_id": 1}})
        
        # Add facet stage to get both data and count in one operation
        pipeline.append({
            "$facet": {
                "data": [
                    {"$skip": skip},
                    {"$limit": limit}
                ],
                "count": [
                    {"$count": "total"}
                ]
            }
        })
        
        # Execute aggregation and extract results
        results = await cls.aggregate(pipeline)
        
        data_list = results[0]["data"] if results and results[0] else []
        count_list = results[0]["count"] if results and results[0] else []
        total = count_list[0]["total"] if count_list else 0
        
        # Convert results to model instances
        data = [cls(**item) for item in data_list]
        
        return {
            "meta": {
                "total": total,
                "displaying": len(data),
                "skip": skip,
                "current_page": skip // limit + 1,
                "per_page": limit,
                "last_page": (total + limit - 1) // limit
            },
            "data": data
        }

    @classmethod
    async def find_by_id(cls: type[T], _id: str | ObjectId) -> Optional[T]:
        object_id = ObjectId(_id) if isinstance(_id, str) else _id
        return await cls.find_one({'_id': object_id})

    @classmethod
    async def find(cls: type[T], query: dict[str, Any], **kwargs) -> list[T]:
        final_query = await cls.query_modifier(query, "find", cls.collection_name())
        results = await cls.exec_find(final_query, **kwargs)
        return [cls(**data) for data in results]

    @classmethod
    async def find_one(cls: type[T], query: dict[str, Any], **kwargs) -> Optional[T]:
        final_query = await cls.query_modifier(query, "find_one", cls.collection_name())
        data = await cls.exec_find_one(final_query, **kwargs)
        return cls(**data) if data else None

    @classmethod
    async def find_or_fail(cls: type[T], query: dict[str, Any], **kwargs) -> T:
        instance = await cls.find_one(query, **kwargs)
        if not instance:
            raise ModelNotFoundException(cls.__name__)
        return instance

    @classmethod
    async def find_by_id_or_fail(cls: type[T], _id: str | ObjectId) -> T:
        object_id = ObjectId(_id) if isinstance(_id, str) else _id
        return await cls.find_or_fail({'_id': object_id})

    @classmethod
    async def exists(cls, query: dict[str, Any]) -> bool:
        final_query = await cls.query_modifier(query, "count", cls.collection_name())
        return await cls.exec_count(final_query) > 0

    @classmethod
    async def first(cls: type[T], **kwargs) -> Optional[T]:
        return await cls.find_one({}, **kwargs)

    @classmethod
    async def find_one_or_create(cls: type[T], query: dict[str, Any], data: Optional[dict[str, Any]] = None) -> T:
        if data is None:
            data = {}
            
        instance = await cls.find_one(query)
        if instance:
            return instance
        return await cls.create({**query, **data})

    @classmethod
    async def delete_many(cls, query: dict[str, Any], **kwargs) -> None:
        coll = await cls.collection_cls()
        final_query = await cls.query_modifier(query, "delete_many", cls.collection_name())
        await coll.delete_many(final_query, **kwargs)
        bump_collection_version(cls.collection_name())

    async def delete(self) -> None:
        await self._notify_observer('on_deleting')
        coll = await self.collection()
        query = await self.query_modifier({'_id': self._id}, "delete", self.collection_name())
        await coll.delete_one(query)
        bump_collection_version(self.collection_name())
        await self._notify_observer('on_deleted')

    @classmethod
    async def update_many(cls, query: dict[str, Any], data: dict[str, Any], **kwargs) -> None:
        coll = await cls.collection_cls()
        final_query = await cls.query_modifier(query, "update_many", cls.collection_name())
        update_data = cls._build_update_payload(set_values=data.get("$set"), extra_ops={k: v for k, v in data.items() if k != "$set"}, touch_timestamp=True)
        await coll.update_many(final_query, update_data, **kwargs)
        bump_collection_version(cls.collection_name())

    async def update(self, data: dict[str, Any]) -> Self:
        for key, value in data.items():
            self.clean[key] = self.get(key)
            setattr(self, key, value)
        await self.save()
        return self

    async def touch(self) -> Self:
        coll = await self.collection()
        query = await self.query_modifier({'_id': self._id}, "touch", self.collection_name())
        await coll.update_one(query, {"$currentDate": {"updated_at": True}})
        await self.refresh()
        bump_collection_version(self.collection_name())
        return self

    @classmethod
    async def count(cls, query: dict[str, Any] = None, **kwargs) -> int:
        final_query = await cls.query_modifier(query, "count", cls.collection_name())
        return await cls.exec_count(final_query, **kwargs)

    @classmethod
    async def aggregate(cls, pipeline: list[dict[str, Any]], **kwargs) -> list[dict[str, Any]]:
        cursor: AsyncIOMotorCommandCursor = (await cls.collection_cls()).aggregate(pipeline, **kwargs)
        return await cursor.to_list(length=None)

    @classmethod
    async def insert_many(cls, data: list[dict[str, Any]]) -> None:
        base_meta = await cls.query_modifier({'created_at': now(), 'updated_at': now()}, "insert_many", cls.collection_name())
        for d in data:
            d.update(base_meta)

        await (await cls.collection_cls()).insert_many(data)
        bump_collection_version(cls.collection_name())

    @classmethod
    async def update_or_create(cls: type[T], query: dict[str, Any], data: dict[str, Any]) -> T:
        instance = await cls.find_one(query)
        if instance:
            await instance.update(data)
        else:
            instance = await cls.create({**query, **data})
        return instance

    def is_dirty(self, key: str) -> bool:
        return key in self.clean

    def get(self, key: str, default: Any = None) -> Any:
        attr = getattr(self, key, default)
        return attr if attr is not None else default

    def set(self, key: str, value: Any) -> None:
        if not self.is_dirty(key):
            self.clean[key] = self.get(key)
        setattr(self, key, value)

    @property
    def id(self) -> Optional[ObjectId]:
        return self._id

    def __setattr__(self, key: str, value: Any) -> None:
        """Override the default setattr to track changes to the model."""
        if key in self.model_fields().keys():
            if not self.is_dirty(key):
                self.clean[key] = self.get(key)

        super().__setattr__(key, value)

    def dict(self, *args, **kwargs):
        """Override the default dict method."""
        data = {key: serialise(getattr(self, key)) for key in self.all_fields()}
        return data

    @classmethod
    async def query_modifier(cls, query: dict, function_name: str = None, model_name: str = None) -> dict:
        return query
    
    @classmethod
    def scope(cls, query=None):
        """Initialize a query builder with optional starting query"""
        return QueryBuilder(cls, query or {})

    #
    # Observers
    #
    def register_observer(self, observer: 'Observer'):
        """Register an observer for this model."""
        self.observers.append(observer)

    #
    # Relationships
    #
    def _get_object_id(self, key: str) -> ObjectId:
        val = getattr(self, key)
        return val if isinstance(val, ObjectId) else ObjectId(val)

    async def belongs_to(self, parent_model, parent_key=None, child_key=None, is_object_id=True) -> Optional['T']:
        parent_model = parent_model
        parent_key = parent_key or '_id'
        child_key = child_key or f'{parent_model.__name__.lower()}_id'
        if getattr(self, child_key, None) is None:
            return None

        return await parent_model.find_one({parent_key: self._get_object_id(child_key) if is_object_id else getattr(self, child_key)})

    async def has_one(self, child_model, parent_key=None, child_key=None) -> Optional['T']:
        child_model = child_model
        parent_key = parent_key or '_id'
        child_key = child_key or f'{self.__class__.__name__.lower()}_id'
        if getattr(self, parent_key, None) is None:
            return None

        return await child_model.find_one({child_key: self._get_object_id(parent_key)})

    async def has_many(self, child_model, parent_key=None, child_key=None) -> list['T']:
        child_model = child_model
        parent_key = parent_key or '_id'
        child_key = child_key or f'{self.__class__.__name__.lower()}_id'
        if getattr(self, parent_key, None) is None:
            return []

        return await child_model.find({child_key: self._get_object_id(parent_key)}, sort=[("_id", -1)])
