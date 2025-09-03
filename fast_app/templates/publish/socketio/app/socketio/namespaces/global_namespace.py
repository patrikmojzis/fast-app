from socketio import AsyncServer, AsyncNamespace
# from app.socketio.common.authentication import authenticate
# from fast_app.decorators.namespace_decorator import register_room

# @register_room(ChatExampleRoom)   # ← injects on_join_chat_example / on_leave_chat_example
class GlobalNamespace(AsyncNamespace):
    def __init__(self):
        super().__init__("/")

    async def on_connect(self, sid, environ, auth):
        # await authenticate(self, sid, environ, auth)
        pass

    async def on_disconnect(self, sid):
        pass