from app.http_files.resources.user_resource import UserResource
from app.http_files.schemas.user_schema import UserSchema
from app.models.user import User
from quart import Response, g

async def show():
    return UserResource(g.user)

async def update(data: UserSchema):
    user = await g.user.update(g.validated)
    return UserResource(user)

async def destroy():
    await g.user.destroy()
    return Response(status=204)
