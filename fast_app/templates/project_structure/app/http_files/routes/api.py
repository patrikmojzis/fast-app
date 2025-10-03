from app.http_files.controllers import user_me_controller, auth_controller
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
        Route.get("/me", user_me_controller.show),
        Route.patch("/me", user_me_controller.update),
        Route.delete("/me", user_me_controller.destroy),
    ])
]
