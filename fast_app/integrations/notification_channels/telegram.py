import ssl

import aiohttp


async def send_via_telegram(text: str, bot_token: str, chat_id: str):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2"
    }

    # Create SSL context that doesn't verify certificates (for environments with SSL issues)
    ssl_context = ssl.create_default_context()
    ssl_context.check_hostname = False
    ssl_context.verify_mode = ssl.CERT_NONE
            
    connector = aiohttp.TCPConnector(ssl=ssl_context)

    async with aiohttp.ClientSession(connector=connector) as session:
        async with session.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload
        ) as response:
            if response.status != 200:
                raise Exception(f"Failed to send to Telegram: {response.status}")