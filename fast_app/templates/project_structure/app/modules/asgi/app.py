import fast_app.boot  # noqa: F401

# Use simple quart app
from .quart import create_quart_app

app = create_quart_app()


# ---- OR use with socketio ----
# run `fast-app publish socketio`
#
#
# from .quart import create_quart_app
# from .socketio import create_socketio_app
# import socketio

# quart_app = create_quart_app()
# socketio_app = create_socketio_app()

# app = socketio.ASGIApp(socketio_app, quart_app)