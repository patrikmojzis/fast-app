from pydantic import BaseModel, Field, field_validator
from typing import Any, Optional
import time
from fast_app.utils.serialisation import pascal_case_to_snake_case, remove_suffix
import time
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from fast_app.utils.serialisation import pascal_case_to_snake_case


class WebsocketEvent(BaseModel):
    type: Optional[str] = Field(None, description="The type of the event")
    data: Optional[Any] = Field(None, description="The data of the event")
    timestamp: int = Field(default_factory=lambda: int(time.time()))

    @field_validator("type")
    @classmethod
    def validate_type(cls, v: Optional[str]) -> str:
        if v is None:
            return remove_suffix(pascal_case_to_snake_case(cls.__name__), "_event")
        return v