from typing import TYPE_CHECKING

from fast_app import Resource

if TYPE_CHECKING:
    from app.models.auth import Auth

class AuthResource(Resource):

    def to_dict(self, auth: 'Auth'):
        return {
            "token_type": "bearer",
            "access_token": auth.refresh_token,
            "refresh_token": auth.create_access_token(),
        }