"""Utility helpers for sending notifications to Slack."""

from typing import Dict

import aiohttp


async def send_via_slack(payload: Dict, webhook_url: str) -> None:
    """Send a JSON payload to a Slack webhook URL."""
    async with aiohttp.ClientSession() as session:
        async with session.post(webhook_url, json=payload, headers={"Content-Type": "application/json"}) as response:
            if response.status != 200:
                raise Exception(f"Failed to send to Slack: {response.status}")
