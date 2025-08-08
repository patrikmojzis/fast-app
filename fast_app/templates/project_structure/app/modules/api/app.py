import os

from quart import Quart
from quart_cors import cors

from app.http_files.routes.api import routes
from app.http_files.routes.ws import routes as ws_routes
from fast_app.utils.routing_utils import register_routes

def get_cors_origins() -> list[str]:
    """Get CORS origins based on environment."""
    env = os.getenv("ENV")
    if env == "debug":
        return [
            # Add your CORS origins here
        ]
    elif env == "prod":
        return [
            # Add your CORS origins here
        ]
    elif env == "dev":
        return [
            # Add your CORS origins here
        ]
    else:
        raise ValueError("Invalid environment")

def create_app() -> Quart:
    """Create and configure the Quart application."""
    app = Quart(__name__)
    app.secret_key = os.getenv("SECRET_KEY")
    
    # Configure CORS
    cors(app, allow_origin=get_cors_origins(), allow_credentials=True)
    
    # Configure HTTP routes
    register_routes(app, routes)
    # Configure WebSocket routes
    register_routes(app, ws_routes)
    
    return app
