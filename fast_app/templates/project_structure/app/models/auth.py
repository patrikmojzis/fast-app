from __future__ import annotations

from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Optional, ClassVar

from app.observers.auth_observer import AuthObserver
from bson import ObjectId

from fast_app import ASC, Index, Model, register_observer, create_access_token
from fast_app.core.jwt_auth import hash_token_value
from fast_app.utils.datetime_utils import now

if TYPE_CHECKING:
    from app.models.user import User


@register_observer(AuthObserver)
class Auth(Model):

    indexes: ClassVar[list[Index]] = [
        Index(
            keys=[("refresh_token_hash", ASC)],
            name="auth_refresh_token_hash",
            unique=True,
            sparse=True,
        )
    ]

    refresh_token_hash: str = None
    user_id: ObjectId = None  # Reference to user
    expires_at: datetime = None  # Token expiry time
    identifier: Optional[str] = None  # Optional device identification or login source
    user_agent: Optional[str] = None  # Optional user agent
    ip_address: Optional[str] = None  # Optional IP address
    is_revoked: bool = False  # Token revocation status
    last_used_at: Optional[datetime] = None  # When token was last used

    @classmethod
    async def revoke_all_for_user(cls, user_id: ObjectId) -> None:
        """Revoke all refresh tokens for a user (useful for logout all devices)."""
        await cls.update_many(
            {'user_id': user_id, 'is_revoked': {"$ne": True}},
            {'$set': {'is_revoked': True}}
        )
    
    @classmethod
    async def cleanup_expired(cls, grace_period_days: int = 30) -> None:
        """Remove expired refresh tokens from database."""
        await cls.delete_many({
            'expires_at': {'$lt': now() - timedelta(days=grace_period_days)}
        })
    
    @classmethod
    async def scope_is_valid(cls, query: dict) -> dict:
        """Check if this refresh token is valid (not expired or revoked)."""
        query['is_revoked'] = {"$ne": True}
        return query

    async def user(self) -> Optional['User']:
        """Get the user associated with this refresh token."""
        from app.models.user import User
        return await self.belongs_to(User)
    
    async def revoke(self) -> None:
        """Revoke this refresh token."""
        await self.update({'is_revoked': True})

    async def revoke_all(self) -> None:
        """Revoke all refresh tokens for the user."""
        await self.revoke_all_for_user(self.user_id)

    def create_access_token(self) -> str:
        """Create an access token for the user."""
        return create_access_token(self.user_id, self.id)

    def set_refresh_token(self, token: str) -> None:
        self._plain_refresh_token = token
        self.refresh_token_hash = self.hash_refresh_token(token)

    @property
    def refresh_token(self) -> str:
        token = getattr(self, "_plain_refresh_token", None)
        if token is None:
            raise RuntimeError("Refresh token is only available on newly issued auth sessions.")
        return token

    @staticmethod
    def hash_refresh_token(token: str) -> str:
        return hash_token_value(token)
