from abc import ABC, abstractmethod
from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional
import redis.asyncio as redis
import os
import time
from fast_app import Resource
from fast_app.utils.serialisation import pascal_case_to_snake_case

class WebsocketEvent(BaseModel):
    type: Optional[str] = Field(None, description="The type of the event")
    data: Optional[Any] = Field(None, description="The data of the event")
    timestamp: int = Field(default_factory=lambda: int(time.time()))

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> str:
        if v is None:
            return pascal_case_to_snake_case(cls.__name__).rstrip("_event")
        return v