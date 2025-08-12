from datetime import datetime, timedelta
from typing import TYPE_CHECKING

from quart import has_request_context, request

from fast_app import Observer, create_refresh_token, REFRESH_TOKEN_LIFETIME, get_client_ip

if TYPE_CHECKING:
    from app.models.auth import Auth

class AuthObserver(Observer):
    """Observer to handle JWT token operations."""

    async def on_creating(self, auth: 'Auth'):
        """
        Set up refresh token when creating.
        Extract expiry and JWT ID from the token itself.
        """
        if not auth.user_id:
            raise ValueError("field `user_id` is required")

        if has_request_context():
            if not auth.ip_address:
                auth.ip_address = get_client_ip()
            if not auth.user_agent:
                auth.user_agent = request.headers.get('User-Agent')

        auth.refresh_token = create_refresh_token(auth.user_id)
        auth.expires_at = datetime.now() + timedelta(seconds=REFRESH_TOKEN_LIFETIME)        

