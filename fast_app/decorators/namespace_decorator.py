from __future__ import annotations
from typing import TYPE_CHECKING, Type
from socketio import AsyncNamespace

if TYPE_CHECKING:
    from fast_app import Room

def register_room(*room_classes: Type['Room']):
    """
    Decorate an AsyncNamespace subclass. For each Room class, inject:
      - on_join_<key>(self, sid, data)
      - on_leave_<key>(self, sid, data)
    where <key> is ChatRoom->"chat", DMRoom->"dm", etc.
    """
    def decorator(ns_cls: Type[AsyncNamespace]) -> Type[AsyncNamespace]:
        for rc in room_classes:
            async def on_join(self: AsyncNamespace, sid: str, data: dict, _rc=rc):
                await _rc.handle_join(self, sid, data)

            async def on_leave(self: AsyncNamespace, sid: str, data: dict, _rc=rc):
                await _rc.handle_leave(self, sid, data)

            setattr(ns_cls, f"on_join_{rc.get_room_key()}", on_join)
            setattr(ns_cls, f"on_leave_{rc.get_room_key()}", on_leave)

        return ns_cls
    return decorator