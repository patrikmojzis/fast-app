import os

from app.http_files.routes.api import routes as api_routes
from quart import Quart
from quart_cors import cors

from fast_app.utils.routing_utils import register_routes
from app.modules.asgi.cors import get_cors_origins


def create_quart_app() -> Quart:
    """Create and configure the Quart application."""
    app = Quart(__name__)
    app.secret_key = os.getenv("SECRET_KEY")
    
    # Configure CORS
    cors(app, allow_origin=get_cors_origins(), allow_credentials=True)
    
    # Configure HTTP routes
    register_routes(app, api_routes)
    
    return app