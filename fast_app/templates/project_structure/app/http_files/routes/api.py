from quart import Quart
from app.http_files.controllers import user_controller, auth_controller, file_controller
from fast_app import Route
from app.http_files.middlewares.auth_middleware import AuthMiddleware

routes = [
    # Authentication routes
    Route.group("/auth", routes=[
        Route.post("/refresh", auth_controller.refresh),
        Route.get("/logout", auth_controller.logout, [AuthMiddleware]),
        Route.get("/logout-all", auth_controller.logout_all, [AuthMiddleware]),
    ]),
    
    # User routes (protected)
    Route.group("/user", middlewares=[AuthMiddleware], routes=[
        Route.get("/current", user_controller.current),
        Route.patch("/<user_id>", user_controller.update),
        Route.delete("/<user_id>", user_controller.destroy),
    ]),
    
    # File management routes
    Route.group("/files", routes=[
        # Public file access (no auth required)
        Route.get("/public/<path:file_path>", file_controller.download_public),
        Route.get("/stream/<path:file_path>", file_controller.stream),
        
        # Protected file operations (auth required)
        Route.group("", middlewares=[AuthMiddleware], routes=[
            Route.post("/upload", file_controller.upload),
            Route.get("/download/<path:file_path>", file_controller.download_user_file),
            Route.get("/info/<path:file_path>", file_controller.info),
            Route.delete("/<path:file_path>", file_controller.delete_file),
        ]),
    ])
]
