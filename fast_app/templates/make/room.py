from typing import Any, Optional
from fast_app import Room

class NewClass(Room):
    @classmethod
    async def extract_room_identifier(cls, session: Any, data: Any) -> str:
        return "room_name"

    @classmethod
    async def can_join(cls, session: Any, data: Any) -> bool:
        return True