from app.http_files.resources.user_resource import UserResource
from quart import g

from app.http_files.middlewares.auth_middleware import protected_route
from fast_app import handle_exceptions
from fast_app.common.simple_controller import simple_destroy, simple_show, simple_update
from app.models.user import User
from app.http_files.schemas.user_schema import UserSchema


async def current(*args, **kwargs):
    return await simple_show(g.user.id, Model=User, Resource=UserResource)

async def update(user_id: str, *args, **kwargs):
    return await simple_update(user_id, Model=User, Resource=UserResource, Schema=UserSchema)

async def destroy(user_id: str, *args, **kwargs):
    return await simple_destroy(user_id, Model=User)