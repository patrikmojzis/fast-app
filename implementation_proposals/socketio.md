# Socket.io

## Set up
```python
sio = socketio.AsyncServer(async_mode="asgi", client_manager=redis, cors_allowed_origins="*")
```

- use redis as that session manager
- share cors with quart


## Authnetication

*on_connect:*

we need a common function that can authenticate user

```python
@sio.event
async def connect(sid, environ, auth):
    token = auth.get("token") if auth else None
    auth_res = authenticate(token)

    if auth_res.invalid:
        raise ConnectionRefusedError("unauthorized")

    await sio.save_session(sid, {"user": auth_res.user})
```

this can be turned into `authenticate_socketio` fnc
```python
async def authenticate_socketio(auth):
    token = auth.get("token") if auth else None
    auth_res = authenticate(token)

    if auth_res.invalid:
        raise ConnectionRefusedError("unauthorized")

    await sio.save_session(sid, {"user": auth_res.user})
    await sio.save_session(sid, {"user_id": auth_res.user.id})
    # set contextvars?
```


**on_channel_join**
(room join)

- connect with `BrodcastChannel` (idea: rename BrodcastChannel to something else?)
- sync with `can_listen` 

```python
@sio.event
async def join_chat(sid, data):
    session = await sio.get_session(sid)
    user = session.get("user")
    chat_id = data.get("chat_id")

    if not chat_id:
        return await sio.emit("error", {"message": "chat_id required"}, to=sid)

    # ❗ Authorize: check the user is allowed to access this chat
    if not await user_can_access_chat(user["id"], chat_id):
        return await sio.emit("error", {"message": "forbidden"}, to=sid)

    sio.enter_room(sid, f"chat:{chat_id}")
    await sio.emit("joined", {"chat_id": chat_id}, to=sid)
```

maybe implementation here can be like:

```python
await ChatChannel("user?").create(sio)
```

```python
class BrodcastChannel:
    async def get_channel_name(self) -> str:
        return pascal_case_to_snake_case(self.__class__.__name__).rstrip("_channel")

    @abstract_method
    async def parse_join_room_name(user, data) -> str:
        pass

    @abstract_method
    async def parse_broadcast_room_name(user, event) -> str:
        pass

    @static_method
    async def handle_join(sid, data):
        session = await sio.get_session(sid)
        user = session.get("user")

        if not self.can_listen(user, data):
            await sio.emit("forbidden")
        

        sio.enter_room(sid, await self.get_room_name())

    @class_method
    async def create(cls, sio):
        sio.event(f"join_{self.channel_name()}", handler=handle_join)
        sio.event(f"leave_{self.channel_name()}", handler=handle_leave)


class ChatChannel(BroadcastChannel):

    async def parse_join_room_name(user, data) -> str:
        if not data.get("room_id"):
            raise

        return f"chat:{data.get('room_id')}"

    async def to_room(chat_id: str) -> str:
        return f"chat:{chat_id}"
        
```


## Setting up events

autodiscover all from: app/socketio_events/*.py

```python
def register_socketio_events(sio):

    await ChatChannel.create(sio)

    @sio.event
    async def some_event(**args):
        pass

    @sio.event
    async def connect():
        UserChannel.join(sid)
```


## Broadcasting

```python
class MessageEvent():
    # pydantic data fields
    async def broadcast_to():
        return [ChatChannel.to_room(self.chat_id), BusinessMonitoringChatChannel.to_room(business().id)]

class MessageEvent():
    # pydantic data fields
    async def broadcast_to():
        return [f"chat:{self.chat_id}", f"business_monitoring_chat:{business().id}"]


broadcast(MessageEvent(text="msg", chat_id=chat.id))
```



----


revisioned:

**BASE:**

```python

class Room:
    def __init__(*args, *kwargs):
        pass

    @abstract_method
    async def room_name(self):
        pass

    async def enter(sio: socketio.AsyncServer):
        sio.enter_room(sid, await self.room_name())


class ChatRoom(Room):
    def __init__(chat_id: str):
        self.chat_id = chat_id

    async def room_name():
        return f"chat:{self.chat_id}"

```

**WITH VERIFICATION:**

```python

class Room:
    def __init__(*args, *kwargs):
        pass        

    @abstract_method
    async def room_name(self):
        pass

    async def enter(sio: socketio.AsyncServer):
        sio.enter_room(sid, await self.room_name())

    async def leave(sio: socketio.AsyncServer):
        sio.leave_room(sid, await self.room_name())

    @class_method
    async def can_join(cls, user, data):
        return True

    @abstract_method
    @class_method
    async def extract_room_name_from_payload(cls, data) -> str:
        """Return string or raise"""
        pass

    @class_method
    async def create(cls, sio: socketio.AsyncServer):

        async def handle_join(sid, data):
            session = await sio.get_session(sid)
            user = session.get("user")

            if not cls.can_join(user, data):
                await sio.emit("forbidden")

            room_name = cls.extract_room_name_from_payload(data)
            sio.enter_room(sid, room_name)


        async def handle_leave(sid, data):
            room_name = cls.extract_room_name_from_payload(data)
            sio.leave_room(sid, room_name)
            

        name = pascal_case_to_snake_case(self.__class__.__name__).rstrip("_room")
        sio.event(f"join_{name}", handler=handle_join)
        sio.event(f"leave_{name}", handler=handle_leave)


class ChatRoom(Room):
    def __init__(chat_id: str):
        self.chat_id = chat_id

    async def room_name():
        return f"chat:{self.chat_id}"

    @class_method
    async def extract_room_name_from_payload(cls, data):
        if not data.get("room_id"):
            raise

        return f"chat:{data.get('room_id')}"

```