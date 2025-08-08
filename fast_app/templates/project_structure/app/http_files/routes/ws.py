from app.http_files.controllers import ws_controller
from fast_app import Route

routes = [
    Route.group("/ws", routes=[
        Route.websocket("/", ws_controller.handle_ws),
    ]),
]

