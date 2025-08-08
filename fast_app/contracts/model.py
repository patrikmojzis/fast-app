# app/models/model_base.py
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TypeVar, ClassVar, Any, get_type_hints
from typing import TYPE_CHECKING

from bson import ObjectId
from pymongo import TEXT

from fast_app.database.mongo import get_db
from fast_app.decorators.db_cache_decorator import cached
from fast_app.exceptions.common_exceptions import DatabaseNotInitializedException
from fast_app.exceptions.model_exceptions import ModelNotFoundException
from fast_app.policy_base import Policy
from fast_app.utils.serialisation import serialise
from fast_app.utils.query_builder import QueryBuilder
from fast_app.utils.model_utils import build_search_query_from_string

if TYPE_CHECKING:
    from motor.motor_asyncio import AsyncIOMotorCollection, AsyncIOMotorCommandCursor
    from fast_app.observer_base import Observer

T = TypeVar('T', bound='Model')


@dataclass
class Model():
    protected: ClassVar[list[str]] = ["_id", "created_at", "updated_at"]

    policy: ClassVar['Policy'] = None
    search_relations: ClassVar[list[dict[str, str]]] = []  # Example: [{"field": "user_id", "model": "User", "search_fields": ["name"]}]

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
    async def collection_cls(cls) -> 'AsyncIOMotorCollection':
        db = await get_db()
        if db is None:
            raise DatabaseNotInitializedException()
        return db[cls.__name__.lower()]

    async def collection(self) -> 'AsyncIOMotorCollection':
        db = await get_db()
        if db is None:
            raise DatabaseNotInitializedException()
        return db[self.__class__.__name__.lower()]

    async def save(self: T) -> T:
        if self._id:
            await self._update()
        else:
            await self._create()
        await self.refresh()
        return self

    @classmethod
    def model_fields(cls) -> dict[str, Any]:
        annotations = {}
        for base in cls.__mro__:
            if hasattr(base, '__annotations__'):
                annotations.update(get_type_hints(base))

        del annotations["protected"]
        del annotations["policy"]
        del annotations["search_relations"]

        return annotations

    @classmethod
    def fillable_fields(cls) -> list[str]:
        return [f for f in cls.model_fields().keys() if f not in cls.protected]

    @classmethod
    def all_fields(cls) -> list[str]:
        return [key for key in cls.model_fields().keys()]

    async def _update(self):
        [await observer.on_updating(self) for observer in self.observers]
        await (await self.collection()).update_one(
            self.query_modifier({'_id': self._id}),
            {
                '$set': {key: self.get(key) for key in self.fillable_fields()},
                '$currentDate': {'updated_at': True}
            }
        )
        await self.refresh()
        [await observer.on_updated(self) for observer in self.observers]

    async def _create(self):
        [await observer.on_creating(self) for observer in self.observers]
        data = self.query_modifier({
            **{key: self.get(key) for key in self.fillable_fields()},
            'created_at': self.get('created_at') or datetime.now(),
            'updated_at': self.get('updated_at') or datetime.now(),
        })
        result = await (await self.collection()).insert_one(data)
        self._id = result.inserted_id
        await self.refresh()
        [await observer.on_created(self) for observer in self.observers]

    @classmethod
    async def create(cls: type[T], data: dict[str, any]) -> T:
        instance = cls(**cls.query_modifier(data))
        await instance.save()
        return instance

    @classmethod
    @cached()
    async def all(cls: type[T]) -> list[T]:
        query = cls.query_modifier({})  
        if cls.policy:  # Apply policy 
            query = await cls.policy.find(query)
        return [cls(**data) async for data in (await cls.collection_cls()).find(query)]

    async def refresh(self: T) -> T:
        data = await (await self.collection()).find_one({'_id': self._id})
        if data:
            for key, value in data.items():
                setattr(self, key, value)
            self.clean = {}
        return self

    @classmethod
    async def search(cls: type[T], query: str | dict[str, any] | ObjectId | int, limit: int = 10, skip: int = 0, 
                                   sort: Optional[list[tuple[str, int]]] = None) -> dict[str, any]:
        """
        Search for records in the current collection and related collections.
        """
        # Convert query to string if it's an int or ObjectId
        if isinstance(query, int):
            query = str(query)
        elif isinstance(query, ObjectId):
            query = {"$or": [{key: query} for key in cls.all_fields()]}
            
        current_collection = cls.__name__.lower()
        
        # Start with direct matches in the current collection
        pipeline = []
        
        # Query for current collection
        base_query = cls.query_modifier() 
        if cls.policy:
            base_query = await cls.policy.find(base_query)  # apply policy
        
        # Find direct matches first
        direct_match = {
            "$match": {
                "$and": [
                    base_query,
                    build_search_query_from_string(query, cls.all_fields()) if isinstance(query, str) else query # Build query from string or use custom
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
                search_fields = relation["search_fields"]
                                
                # Add unionWith to include related matches
                pipeline.append({
                    "$unionWith": {
                        "coll": related_model_name,
                        "pipeline": [
                            # Find documents in the related collection matching the search query
                            {"$match": {
                                "$and": [
                                    cls.query_modifier(),
                                    build_search_query_from_string(query, search_fields)
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
                "limit": limit,
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
        return await cls.find_one(cls.query_modifier({'_id': object_id}))

    @classmethod
    @cached()
    async def find(cls: type[T], query: dict[str, any], **kwargs) -> list[T]:
        if cls.policy:  # Apply policy 
            query = await cls.policy.find(query)
        return [cls(**data) async for data in (await cls.collection_cls()).find(cls.query_modifier(query), **kwargs)]

    @classmethod
    @cached()
    async def find_one(cls: type[T], query: dict[str, any], **kwargs) -> Optional[T]:
        if cls.policy:  # Apply policy 
            query = await cls.policy.find(query)
        data = await (await cls.collection_cls()).find_one(cls.query_modifier(query), **kwargs)
        return cls(**data) if data else None

    @classmethod
    async def find_or_fail(cls: type[T], query: dict[str, any], **kwargs) -> T:
        instance = await cls.find_one(cls.query_modifier(query), **kwargs)
        if not instance:
            raise ModelNotFoundException(cls.__name__)
        return instance

    @classmethod
    async def find_by_id_or_fail(cls: type[T], _id: str | ObjectId) -> T:
        object_id = ObjectId(_id) if isinstance(_id, str) else _id
        return await cls.find_or_fail(cls.query_modifier({'_id': object_id}))

    @classmethod
    @cached()
    async def exists(cls, query: dict[str, any]) -> bool:
        if cls.policy:  # Apply policy 
            query = await cls.policy.find(query)
        return await (await cls.collection_cls()).count_documents(cls.query_modifier(query)) > 0

    @classmethod
    async def first(cls: type[T], **kwargs) -> Optional[T]:
        return await cls.find_one(cls.query_modifier({}), **kwargs)

    @classmethod
    async def delete_many(cls, query: dict[str, any], **kwargs) -> None:
        await (await cls.collection_cls()).delete_many(cls.query_modifier(query), **kwargs)

    async def delete(self) -> None:
        [await observer.on_deleting(self) for observer in self.observers]
        await (await self.collection()).delete_one(self.query_modifier({'_id': self._id}))
        [await observer.on_deleted(self) for observer in self.observers]

    @classmethod
    async def update_many(cls, query: dict[str, any], data: dict[str, any], **kwargs) -> None:
        # Initialize the update data with the updated_at field
        update_data = {"$set": {"updated_at": datetime.now()}}

        # Merge the provided data into the update_data
        for key, value in data.items():
            if key == "$set":
                # If the key is "$set", merge its contents with the existing "$set" in update_data
                if "$set" in update_data:
                    update_data["$set"].update(value)
                else:
                    update_data["$set"] = value
            else:
                # For other operations like "$unset", simply add/merge them
                update_data[key] = value

        await (await cls.collection_cls()).update_many(cls.query_modifier(query), update_data, **kwargs)

    async def update(self: T, data: dict[str, any]) -> T:
        for key, value in data.items():
            self.clean[key] = self.get(key)
            setattr(self, key, value)
        await self.save()
        return self

    @classmethod
    @cached()
    async def count(cls, query: dict[str, any] = None, **kwargs) -> int:
        if cls.policy:  # Apply policy 
            query = await cls.policy.find(query)
        return await (await cls.collection_cls()).count_documents(cls.query_modifier(query), **kwargs)

    @classmethod
    @cached()
    async def aggregate(cls, pipeline: list[dict[str, any]], **kwargs) -> list[dict[str, any]]:
        cursor: AsyncIOMotorCommandCursor = (await cls.collection_cls()).aggregate(pipeline, **kwargs)
        return await cursor.to_list(length=None)

    @classmethod
    async def insert_many(cls, data: list[dict[str, any]]) -> None:
        for d in data:
            d.update(cls.query_modifier({'created_at': datetime.now(), 'updated_at': datetime.now()}))

        await (await cls.collection_cls()).insert_many(data)

    @classmethod
    async def update_or_create(cls: type[T], query: dict[str, any], data: dict[str, any]) -> T:
        instance = await cls.find_one(cls.query_modifier(query))
        if instance:
            await instance.update(data)
        else:
            instance = await cls.create({**query, **data})
        return instance

    def is_dirty(self, key: str) -> bool:
        return key in self.clean

    def get(self, key: str, default: any = None) -> any:
        attr = getattr(self, key, default)
        return attr if attr is not None else default

    def set(self, key: str, value: any) -> None:
        if not self.is_dirty(key):
            self.clean[key] = self.get(key)
        setattr(self, key, value)

    @property
    def id(self) -> Optional[ObjectId]:
        return self._id

    def __setattr__(self, key: str, value: any) -> None:
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
    def query_modifier(cls, query: dict = None) -> dict:
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
