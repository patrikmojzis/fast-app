from app.http_files.controllers import ws_controller
from fast_app.common.routing import Route

routes = [
    Route.group("/ws", routes=[
        Route.websocket("/", ws_controller.handle_ws),
    ]),
]
