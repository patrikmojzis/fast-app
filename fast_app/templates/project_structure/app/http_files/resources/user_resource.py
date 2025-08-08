from fast_app.contracts.resource import Resource

from app.models.user import User
from app.http_files.schemas.user_schema import UserSchema


class UserResource(Resource):
    
    async def to_dict(self, user: User) -> dict:
        return {
            "_id": user.id,
            "name": user.name,
            "email": user.email,
        }   