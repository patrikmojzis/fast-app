from pydantic import Field, constr

from fast_app import Schema


class AuthRefreshSchema(Schema):
    refresh_token: constr(min_length=1) = Field(..., description="Refresh token")