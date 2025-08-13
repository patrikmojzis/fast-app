"""Utility helpers for sending notifications to Slack."""

import ssl
from typing import Dict

import aiohttp


async def send_via_slack(payload: Dict, webhook_url: str) -> None:
    """Send a JSON payload to a Slack webhook URL."""
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(ssl=ssl_context)
    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}) as response:
            if response.status != 200:
                raise Exception(f"Failed to send to Slack: {response.status}")
