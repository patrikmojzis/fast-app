from pydantic import BaseModel, Field, constr


class AuthRefreshSchema(BaseModel):
    refresh_token: constr(min_length=1) = Field(..., description="Refresh token")