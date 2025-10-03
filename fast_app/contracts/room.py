from abc import abstractmethod, ABC
from socketio import AsyncServer, AsyncNamespace
from typing import Dict, Any, Optional, TYPE_CHECKING, Tuple, Awaitable, Union
from fast_app.utils.serialisation import pascal_case_to_snake_case, remove_suffix

if TYPE_CHECKING:
    from fast_app.contracts.broadcast_event import BroadcastEvent

class Room(ABC):
    """
    Base class for socketio rooms.

    Example:
    ```python
    class ChatRoom(Room):
        @classmethod
        async def extract_room_identifier(cls, session: Any, data: Any) -> Union[str, Tuple[str, ...]]:
            if not data.get('chat_id'):
                raise ValueError("chat_id is required")

            return data.get('chat_id')

        @classmethod
        async def can_join(cls, session: Any, data: Any) -> bool:
            chat = await Chat.find_by_id(data.get('chat_id'))
            return chat.is_member(session.get('user'))
    ```

    Register the room entry / leave handlers with the server:
    ```python
    await ChatRoom.register(sio)
    ```
    """

    def __init__(self, *args, namespace: str = "/", room_identifier: Optional[str] = None):
        self.namespace = namespace
        self.room_identifier = room_identifier if room_identifier else "|".join([str(arg) for arg in args])

    @classmethod
    def get_room_key(cls) -> str:
        """
        Room key is the first part of the room name, e.g. class ChatRoom -> "chat"
        """
        return remove_suffix(pascal_case_to_snake_case(cls.__name__), "_room")

    def get_room_name(self) -> str:
        """
        Combines room key and identifier to form room name, e.g. "chat|123"
        """
        return f"{self.get_room_key()}|{self.room_identifier}"

    async def enter(self, sio: AsyncServer, sid: str):
        """
        Use this method to enter the room
        e.g. ChatRoom(chat_id).enter(sio, sid)
        """
        return await sio.enter_room(sid, self.get_room_name())

    async def leave(self, sio: AsyncServer, sid: str):
        """
        Use this method to leave the room
        e.g. ChatRoom(chat_id).leave(sio, sid)
        """
        return await sio.leave_room(sid, self.get_room_name())

    @classmethod
    async def can_join(cls, session: Any, data: Any) -> bool:
        """
        Override per room type; default allow.
        """
        return True

    @classmethod
    async def extract_room_identifier(cls, session: Any, data: Any) -> Union[str, Tuple[str, ...]]:
        """
        Define how to extract room identifier from event's data
        e.g. data.get('room_id')
        or raise ValueError if room name is not found
        """
        raise NotImplementedError("extract_room_identifier must be implemented")

    @classmethod
    async def on_join(cls, sio: AsyncServer | AsyncNamespace, sid: str, room_name: str, data: Any) -> None:
        """Custom hook to be overridden"""
        pass

    @classmethod
    async def on_leave(cls, sio: AsyncServer | AsyncNamespace, sid: str, room_name: str, data: Any) -> None:
        """Custom hook to be overridden"""
        pass

    @classmethod
    async def handle_join(cls, sio: AsyncServer | AsyncNamespace, sid: str, data: Any) -> None:
        session = await sio.get_session(sid)

        # extract room name from payload
        try:
            room_identifier = await cls.extract_room_identifier(session, data)
            room_name = f"{cls.get_room_key()}|{'|'.join(room_identifier)}" if isinstance(room_identifier, tuple) else f"{cls.get_room_key()}|{room_identifier}"
        except ValueError as e:
            await sio.emit("error", {"type": "validation_error", "msg": str(e)}, to=sid)
            return

        # verify can_join gate
        if not await cls.can_join(session, data):
            await sio.emit("error", {"type": "forbidden", "room": room_name}, to=sid)
            return
        
        await sio.enter_room(sid, room_name)
        await sio.emit("joined", to=sid)
        await cls.on_join(sio=sio, sid=sid, room_name=room_name, data=data)

    @classmethod
    async def handle_leave(cls, sio: AsyncServer | AsyncNamespace, sid: str, data: Dict[str, Any]) -> None:
        session = await sio.get_session(sid)

        # extract room name from payload
        try:
            room_identifier = await cls.extract_room_identifier(session, data)
            room_name = f"{cls.get_room_key()}|{'|'.join(room_identifier)}" if isinstance(room_identifier, tuple) else f"{cls.get_room_key()}|{room_identifier}"
        except ValueError as e:
            await sio.emit("error", {"type": "validation_error", "msg": str(e)}, to=sid)
            return

        await sio.leave_room(sid, room_name)
        await sio.emit("left", to=sid)
        await cls.on_leave(sio=sio, sid=sid, room_name=room_name, data=data)

    @classmethod
    async def register(cls, sio: AsyncServer, namespace: Optional[str] = None) -> None:
        """
        Registers 'join_<name>' and 'leave_<name>' handlers for this room type.
        e.g. ChatRoom => 'join_chat' and 'leave_chat'

        Optionally, override `can_join` to gate join.

        Events:
            - On join, emits 'joined' event.
            - On leave, emits 'left' event.
            - On extract_room_name ValueError, emits 'error' event with type 'validation_error'
            - On can_join False, emits 'error' event with type 'forbidden'
        """
        async def handle_join(sid: str, data: Dict[str, Any]):
            await cls.handle_join(sio, sid, data)

        async def handle_leave(sid: str, data: Dict[str, Any]):
            await cls.handle_leave(sio, sid, data)

        sio.on(f"join_{cls.get_room_key()}", handle_join, namespace=namespace)
        sio.on(f"leave_{cls.get_room_key()}", handle_leave, namespace=namespace)

