from app.http_files.controllers import user_controller, auth_controller
from app.http_files.middlewares.auth_middleware import AuthMiddleware

from fast_app import Route

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
    ])
]
