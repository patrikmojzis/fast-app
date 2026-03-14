import aiohttp


async def send_via_telegram(text: str, bot_token: str, chat_id: str):
    payload = {
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "MarkdownV2"
    }

    async with aiohttp.ClientSession() as session:
        async with session.post(
            f"https://api.telegram.org/bot{bot_token}/sendMessage",
            json=payload
        ) as response:
            if response.status != 200:
                raise Exception(f"Failed to send to Telegram: {response.status}")
