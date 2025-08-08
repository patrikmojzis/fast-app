from typing import TYPE_CHECKING

import requests
from exponent_server_sdk import (
    DeviceNotRegisteredError,
    PushClient,
    PushMessage,
    PushServerError,
    PushTicketError,
)
from requests.exceptions import ConnectionError, HTTPError
import os


# Basic arguments. You should extend this function with the push features you
# want to use, or simply pass in a `PushMessage` object.
def send_via_push_notification(push_token: str, title: str, body: str, data: dict = None):
    """
    Send a push notification to a user via Expo.

    Args:
        push_token (str): The push token of the user to send the notification to.
        title (str): The title of the notification.
        body (str): The body of the notification.
        data (dict): The data to send with the notification.

    Raises:
        exponent_server_sdk.PushServerError: If the push notification fails.
        requests.exceptions.ConnectionError: If the connection to the Expo server fails.
        requests.exceptions.HTTPError: If the HTTP request fails.
        exponent_server_sdk.DeviceNotRegisteredError: If the push token is not registered. (Mark push token as inactive)
        exponent_server_sdk.PushTicketError: If the push notification fails.
    """
    session = requests.Session()
    session.headers.update(
        {
            "accept": "application/json",
            "accept-encoding": "gzip, deflate",
            "content-type": "application/json",
        }
    )

    if expo_authorization_token := os.getenv('EXPO_AUTHORIZATION_TOKEN'):
        session.headers.update(
            {
                "Authorization": f"Bearer {expo_authorization_token}",
            }
        )
        
    response = PushClient(session=session).publish(
                    PushMessage(to=push_token,
                        title=title,
                        body=body,
                        data=data,
                        sound="default"))

    response.validate_response()

    return response